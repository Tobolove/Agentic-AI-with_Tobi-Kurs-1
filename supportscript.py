# === INTELLIGENT CUSTOMER SUPPORT ORCHESTRATOR ===
# Complete support system with PostgreSQL integration and LLM-based customer ID extraction

import psycopg2
from psycopg2.extras import RealDictCursor
import json
import os
from openai import AzureOpenAI
from dotenv import load_dotenv

# Load environment variables and initialize OpenAI client
load_dotenv()

# Azure OpenAI Configuration
api_key = os.getenv("AZURE_OPENAI_API_KEY")
azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")

# Model name should match your Azure deployment name
model = azure_deployment if azure_deployment else "gpt-4o-mini"

if not api_key or not azure_endpoint:
    raise ValueError("Azure OpenAI configuration missing. Please set AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, and AZURE_OPENAI_DEPLOYMENT_NAME in your .env file.")

# Configure client for Azure OpenAI
client = AzureOpenAI(
    api_key=api_key,
    api_version=api_version,
    azure_endpoint=azure_endpoint,
)

# --- Helper Function for API Calls ---
def call_openai(system_prompt, user_prompt, model=model, temperature=0.0):
    """Simple wrapper for OpenAI API calls."""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"An error occurred: {e}"

# === SPECIALIZED WORKER AGENTS ===

class TicketAnalyzerAgent:
    """Analyzes support tickets to determine routing and saves them to PostgreSQL database."""
    
    def __init__(self):
        self.connection_string = os.getenv("DATABASE_CUSTOMER_URL")
        if not self.connection_string:
            raise ValueError("DATABASE_CUSTOMER_URL not found in environment variables. Please set it in your .env file.")
    
    def _get_connection(self):
        """Create a database connection."""
        try:
            return psycopg2.connect(
                self.connection_string,
                cursor_factory=RealDictCursor
            )
        except Exception as e:
            print(f"✗ Database connection error: {e}")
            return None
    
    def analyze_ticket(self, ticket_content, customer_id=None):
        system_prompt = """You are a ticket routing specialist. Analyze support tickets and determine:

        1. ticket_type: "billing", "technical", "account", "general_inquiry", "complaint"
        2. urgency: "low", "medium", "high", "critical"
        3. requires_customer_data: true/false (if we need to look up customer information)
        4. requires_technical_help: true/false (if technical problem-solving is needed)
        5. customer_sentiment: "positive", "neutral", "frustrated", "angry"
        6. estimated_resolution_time: "5min", "15min", "30min", "1hour+"

        Return valid JSON with these exact keys."""

        user_prompt = f"Analyze this support ticket:\n\n{ticket_content}"
        
        try:
            response = call_openai(system_prompt, user_prompt)
            if response.strip().startswith("```json"):
                response = response.strip()[7:-3].strip()
            analysis = json.loads(response)
        except:
            # Fallback analysis
            analysis = {
                "ticket_type": "general_inquiry",
                "urgency": "medium", 
                "requires_customer_data": True,
                "requires_technical_help": False,
                "customer_sentiment": "neutral",
                "estimated_resolution_time": "15min"
            }
        
        # Save to database with incoming content
        ticket_id = self._save_ticket_to_db(analysis, customer_id, ticket_content)
        analysis['ticket_id'] = ticket_id
        
        return analysis
    
    def _save_ticket_to_db(self, analysis, customer_id, incoming_content):
        """Save the analyzed ticket to PostgreSQL database."""
        print("Saving ticket to database...")
        
        conn = self._get_connection()
        if not conn:
            print("✗ Could not save ticket - database connection failed")
            return None
        
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO tickets (
                        customer_id, 
                        ticket_type, 
                        urgency, 
                        requires_customer_data, 
                        requires_technical_help, 
                        customer_sentiment, 
                        estimated_resolution_time,
                        incoming_content
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING ticket_id;
                """, (
                    customer_id,
                    analysis['ticket_type'],
                    analysis['urgency'], 
                    analysis['requires_customer_data'],
                    analysis['requires_technical_help'],
                    analysis['customer_sentiment'],
                    analysis['estimated_resolution_time'],
                    incoming_content
                ))
                
                ticket_id = cursor.fetchone()['ticket_id']
                conn.commit()
                
                print(f"✓ Ticket saved with ID: {ticket_id}")
                return ticket_id
                
        except Exception as e:
            print(f"✗ Error saving ticket: {e}")
            conn.rollback()
            return None
        
        finally:
            conn.close()
    
    def update_ticket_recommendation(self, ticket_id, recommended_answer):
        """Update the ticket with the recommended answer."""
        if not ticket_id:
            return
            
        print(f"Updating ticket {ticket_id} with recommended answer...")
        
        conn = self._get_connection()
        if not conn:
            print("✗ Could not update ticket - database connection failed")
            return
        
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE tickets 
                    SET recommended_answer = %s
                    WHERE ticket_id = %s;
                """, (recommended_answer, ticket_id))
                
                conn.commit()
                print(f"✓ Ticket {ticket_id} updated with recommendation")
                
        except Exception as e:
            print(f"✗ Error updating ticket: {e}")
            conn.rollback()
        
        finally:
            conn.close()

class DatabaseQueryAgent:
    """Queries customer database for relevant information from PostgreSQL using only customer_id."""
    
    def __init__(self):
        self.connection_string = os.getenv("DATABASE_CUSTOMER_URL")
        if not self.connection_string:
            raise ValueError("DATABASE_CUSTOMER_URL not found in environment variables. Please set it in your .env file.")
    
    def _get_connection(self):
        """Create a database connection."""
        try:
            return psycopg2.connect(
                self.connection_string,
                cursor_factory=RealDictCursor
            )
        except Exception as e:
            print(f"✗ Database connection error: {e}")
            return None
    
    def query_customer_info(self, customer_id, query_type="full"):
        """Query customer information by customer_id only."""
        print(f"Querying database for customer: {customer_id}")
        
        # Validate customer_id format
        if not customer_id or not customer_id.startswith('CUST'):
            return {"error": f"Invalid customer ID format: {customer_id}. Expected format: CUSTXXX"}
        
        conn = self._get_connection()
        if not conn:
            return {"error": "Database connection failed"}
        
        try:
            with conn.cursor() as cursor:
                if query_type == "billing":
                    cursor.execute("""
                        SELECT name, plan, last_payment, 'Active' as status 
                        FROM customer_support 
                        WHERE customer_id = %s
                    """, (customer_id,))
                    
                elif query_type == "history":
                    cursor.execute("""
                        SELECT name, support_history, join_date 
                        FROM customer_support 
                        WHERE customer_id = %s
                    """, (customer_id,))
                    
                else:  # full
                    cursor.execute("""
                        SELECT customer_id, name, email, plan, join_date, 
                               last_payment, support_history 
                        FROM customer_support 
                        WHERE customer_id = %s
                    """, (customer_id,))
                
                result = cursor.fetchone()
                
                if result:
                    # Convert RealDictRow to regular dict and handle dates
                    customer_data = dict(result)
                    
                    # Convert dates to strings for JSON compatibility
                    if 'join_date' in customer_data and customer_data['join_date']:
                        customer_data['join_date'] = customer_data['join_date'].strftime('%Y-%m-%d')
                    if 'last_payment' in customer_data and customer_data['last_payment']:
                        customer_data['last_payment'] = customer_data['last_payment'].strftime('%Y-%m-%d')
                    
                    # Handle empty support_history array
                    if 'support_history' in customer_data and customer_data['support_history'] is None:
                        customer_data['support_history'] = []
                    
                    return customer_data
                else:
                    return {"error": f"Customer {customer_id} not found in database"}
                    
        except Exception as e:
            print(f"✗ Database query error: {e}")
            return {"error": f"Database query failed: {str(e)}"}
        
        finally:
            conn.close()

class TechnicalProblemSolverAgent:
    """Solves technical problems and provides solutions."""
    
    def solve_technical_issue(self, ticket_content, customer_info=None):
        system_prompt = """You are a technical support expert. Analyze the technical issue and provide:

        1. A clear diagnosis of the problem
        2. Step-by-step solution instructions
        3. Preventive measures
        4. Escalation recommendation if needed

        Be technical but user-friendly in your explanations."""

        context = f"Customer Info: {json.dumps(customer_info) if customer_info else 'Not available'}"
        user_prompt = f"Technical Issue:\n{ticket_content}\n\nContext:\n{context}"
        
        return call_openai(system_prompt, user_prompt)

class EmailReplyAgent:
    """Composes professional email replies to customers."""
    
    def compose_reply(self, ticket_analysis, customer_info, technical_solution=None, ticket_content=""):
        system_prompt = f"""You are a professional customer support representative. Compose a helpful, empathetic email reply IN GERMAN.

Customer sentiment: {ticket_analysis.get('customer_sentiment', 'neutral')}
Ticket urgency: {ticket_analysis.get('urgency', 'medium')}

Guidelines:
- Write the entire email in German
- Be warm and professional (warm und professionell)
- Address the customer by name if available
- Acknowledge their specific concern
- Provide clear, actionable information
- Match the tone to their sentiment (more empathetic if frustrated/angry)
- Include relevant account information when helpful
- End with next steps or additional support offer
- Always sign the email with: "Mit freundlichen Grüssen,\nTobias Frei\nVIVAVIS Schweiz AG"

IMPORTANT: The entire email response must be written in German language."""

        context_info = []
        if customer_info and 'name' in customer_info:
            context_info.append(f"Customer: {customer_info['name']}")
        if customer_info and 'plan' in customer_info:
            context_info.append(f"Plan: {customer_info['plan']}")
        if technical_solution:
            context_info.append(f"Technical Solution: {technical_solution}")
            
        user_prompt = f"""Original ticket: {ticket_content}

Available context:
{chr(10).join(context_info)}

Compose a professional email reply."""

        return call_openai(system_prompt, user_prompt)

# === INTELLIGENT SUPPORT ORCHESTRATOR ===

class IntelligentSupportOrchestrator:
    """
    A true orchestrator that makes intelligent decisions about which agents to use
    and in what order, based on ticket analysis.
    """
    
    def __init__(self):
        # Initialize all available specialist agents
        self.ticket_analyzer = TicketAnalyzerAgent()
        self.database_agent = DatabaseQueryAgent()
        self.tech_solver = TechnicalProblemSolverAgent()
        self.reply_agent = EmailReplyAgent()
        
        print("IntelligentSupportOrchestrator initialized")
        print("Available agents: Analyzer, Database, TechSolver, ReplyAgent")
    
    def extract_customer_id(self, ticket_content):
        """Extract customer ID from ticket content using LLM intelligence."""
        print("Extracting customer ID from ticket...")
        
        system_prompt = """You are a customer ID extraction specialist. Your job is to find customer IDs in support tickets.

Look for customer IDs that follow these patterns:
- CUST001, CUST002, CUST003, etc. (CUST followed by numbers)
- May appear after phrases like "Customer ID:", "Customer:", "Account:", "ID:"

Rules:
1. ONLY extract valid customer IDs that start with "CUST" followed by numbers
2. If you find a valid customer ID, return ONLY that ID (e.g., "CUST001")  
3. If no valid customer ID is found, return "NONE"
4. Do not extract random text that happens to contain "ID"
5. Ignore endpoints, API paths, or other technical terms

Examples:
- "Customer ID: CUST001" → "CUST001"
- "Customer: CUST002" → "CUST002"  
- "Endpoint: /api/v2/data" → "NONE"
- "My ID is John123" → "NONE"

Return ONLY the customer ID or "NONE", nothing else."""

        user_prompt = f"Extract the customer ID from this support ticket:\n\n{ticket_content}"
        
        try:
            response = call_openai(system_prompt, user_prompt)
            extracted_id = response.strip()
            
            # Validate the LLM response
            if extracted_id == "NONE" or not extracted_id.startswith("CUST"):
                print(f"No valid customer ID found")
                return None
            
            print(f"✓ Customer ID extracted: {extracted_id}")
            return extracted_id
            
        except Exception as e:
            print(f"✗ Customer ID extraction failed: {e}")
            return None
    
    def process_support_ticket(self, ticket_content, customer_id=None):
        """
        Intelligently processes a support ticket with dynamic agent routing.
        """
        print(f"\n=== PROCESSING SUPPORT TICKET ===")
        print(f"Ticket preview: {ticket_content[:100]}...")
        
        # Extract customer ID if not provided
        if not customer_id:
            customer_id = self.extract_customer_id(ticket_content)
        
        # === STEP 1: INTELLIGENT ANALYSIS ===
        print(f"\nSTEP 1: Analyzing ticket...")
        ticket_analysis = self.ticket_analyzer.analyze_ticket(ticket_content, customer_id)
        
        print(f"Analysis Results:")
        print(f"   Type: {ticket_analysis['ticket_type']}")
        print(f"   Urgency: {ticket_analysis['urgency']}")
        print(f"   Needs Customer Data: {ticket_analysis['requires_customer_data']}")
        print(f"   Needs Technical Help: {ticket_analysis['requires_technical_help']}")
        print(f"   Customer Sentiment: {ticket_analysis['customer_sentiment']}")
        if customer_id:
            print(f"   Customer ID: {customer_id}")
        if ticket_analysis.get('ticket_id'):
            print(f"   Ticket ID: {ticket_analysis['ticket_id']}")
        
        gathered_data = {"analysis": ticket_analysis}
        
        # === STEP 2: CONDITIONAL DATABASE QUERY ===
        if ticket_analysis['requires_customer_data'] and customer_id:
            print(f"\nSTEP 2: Customer data needed - querying database")
            
            # Smart query type selection based on ticket type
            if ticket_analysis['ticket_type'] == 'billing':
                query_type = 'billing'
                print(f"   Using billing query for billing ticket")
            elif ticket_analysis['ticket_type'] == 'account':
                query_type = 'history'
                print(f"   Using history query for account issue")
            else:
                query_type = 'full'
                print(f"   Using full query for comprehensive context")
            
            customer_info = self.database_agent.query_customer_info(customer_id, query_type)
            gathered_data["customer_info"] = customer_info
            
            if "error" in customer_info:
                print(f"   ✗ Database lookup failed: {customer_info['error']}")
            else:
                print(f"   ✓ Retrieved data for: {customer_info.get('name', 'Unknown')}")
        
        elif ticket_analysis['requires_customer_data']:
            print(f"\nSTEP 2: Customer data needed but no ID found")
            print(f"   Will request customer identification in reply")
            gathered_data["customer_info"] = None
        else:
            print(f"\nSTEP 2: No customer data needed - skipping database")
            gathered_data["customer_info"] = None
        
        # === STEP 3: CONDITIONAL TECHNICAL PROBLEM SOLVING ===
        if ticket_analysis['requires_technical_help']:
            print(f"\nSTEP 3: Technical issue detected - generating solution")
            
            # Priority routing for critical issues
            if ticket_analysis['urgency'] == 'critical':
                print(f"   CRITICAL PRIORITY: Fast-tracking technical analysis")
            
            technical_solution = self.tech_solver.solve_technical_issue(
                ticket_content, 
                gathered_data.get("customer_info")
            )
            gathered_data["technical_solution"] = technical_solution
            print(f"   ✓ Technical solution generated")
        else:
            print(f"\nSTEP 3: No technical help needed - skipping TechSolver")
            gathered_data["technical_solution"] = None
        
        # === STEP 4: INTELLIGENT REPLY COMPOSITION ===
        print(f"\nSTEP 4: Composing final reply")
        
        # Smart urgency handling
        if ticket_analysis['urgency'] in ['high', 'critical']:
            print(f"   High priority handling: Expedited reply generation")
        
        # Sentiment-aware processing
        if ticket_analysis['customer_sentiment'] in ['frustrated', 'angry']:
            print(f"   Sentiment-aware: Applying empathetic tone")
        
        final_reply = self.reply_agent.compose_reply(
            ticket_analysis=ticket_analysis,
            customer_info=gathered_data.get("customer_info"),
            technical_solution=gathered_data.get("technical_solution"),
            ticket_content=ticket_content
        )
        
        # Update ticket with recommended answer
        if ticket_analysis.get('ticket_id'):
            self.ticket_analyzer.update_ticket_recommendation(
                ticket_analysis['ticket_id'], 
                final_reply
            )
        
        # === FINAL ORCHESTRATION SUMMARY ===
        print(f"\n=== ORCHESTRATION SUMMARY ===")
        agents_used = ["TicketAnalyzer"]
        if gathered_data.get("customer_info"):
            agents_used.append("DatabaseAgent")
        if gathered_data.get("technical_solution"):
            agents_used.append("TechSolver")
        agents_used.append("ReplyAgent")
        
        print(f"Agents Used: {' → '.join(agents_used)}")
        print(f"Estimated Resolution Time: {ticket_analysis['estimated_resolution_time']}")
        print(f"Routing Efficiency: {len(agents_used)}/4 agents used")
        
        return {
            "final_reply": final_reply,
            "analysis": ticket_analysis,
            "agents_used": agents_used,
            "customer_info": gathered_data.get("customer_info"),
            "technical_solution": gathered_data.get("technical_solution")
        }

# === DEMONSTRATION FUNCTION ===
def run_demo():
    """Run a demonstration of the intelligent orchestration system."""
    
    # Initialize the intelligent orchestrator
    orchestrator = IntelligentSupportOrchestrator()

    print("\n" + "="*80)
    print("TESTING INTELLIGENT ORCHESTRATION WITH REAL DECISION-MAKING")
    print("="*80)

    # === TEST CASE 1: BILLING INQUIRY (Needs Database, No Tech Support) ===
    print("\nTEST CASE 1: Billing Inquiry")
    print("-" * 50)

    billing_ticket = """
Subject: Frage zu meiner letzten Rechnung
Customer ID: CUST001

Hallo, ich habe meine Rechnung für September erhalten, aber ich bin verwirrt über einige Gebühren.
Können Sie mir bitte erklären, wofür die "Premium Features" Gebühr ist?
Ich kann mich nicht daran erinnern, Premium-Features zu meinem Konto hinzugefügt zu haben.

Vielen Dank,
Sarah
"""

    result1 = orchestrator.process_support_ticket(billing_ticket)
    print(f"\nFINAL REPLY:")
    print(result1['final_reply'][:500] + "..." if len(result1['final_reply']) > 500 else result1['final_reply'])

    # === TEST CASE 2: TECHNICAL ISSUE (Needs Database + Tech Support) ===
    print("\n\nTEST CASE 2: Technical Problem")
    print("-" * 50)

    tech_ticket = """
Subject: DRINGEND - API antwortet nicht
Customer: CUST002

Unsere Produktionsanwendung erhält seit etwa 2 Stunden 500-Fehler von Ihrer API.
Das betrifft unsere Kunden und wir brauchen sofortige Hilfe!

Fehlermeldung: "Connection timeout after 30 seconds"
Endpoint: /api/v2/data/sync

Wir haben den Business-Plan und das ist kritisch für unseren Betrieb.

Mike Chen
CTO, TechCorp
"""

    result2 = orchestrator.process_support_ticket(tech_ticket, "CUST002")
    print(f"\nFINAL REPLY:")
    print(result2['final_reply'][:500] + "..." if len(result2['final_reply']) > 500 else result2['final_reply'])

    # === TEST CASE 3: SIMPLE GENERAL INQUIRY (Minimal Routing) ===
    print("\n\nTEST CASE 3: General Inquiry")
    print("-" * 50)

    general_ticket = """
Subject: Frage zu Ihrem Service

Hallo,
ich überlege, mich für Ihren Service anzumelden und wollte wissen, was im 
Basic-Plan im Vergleich zum Premium-Plan enthalten ist? Bieten Sie auch Studentenrabatte an?

Vielen Dank!
Alex
"""

    result3 = orchestrator.process_support_ticket(general_ticket)
    print(f"\nFINAL REPLY:")
    print(result3['final_reply'][:500] + "..." if len(result3['final_reply']) > 500 else result3['final_reply'])

    # === ORCHESTRATION COMPARISON SUMMARY ===
    print("\n\nINTELLIGENT ORCHESTRATION ANALYSIS")
    print("="*80)
    print(f"Test Case 1 (Billing):    {' → '.join(result1['agents_used'])}")
    print(f"Test Case 2 (Technical):  {' → '.join(result2['agents_used'])}")  
    print(f"Test Case 3 (General):    {' → '.join(result3['agents_used'])}")
    print("\nNotice how the orchestrator intelligently routes to different agents")
    print("based on the actual needs of each ticket - this is TRUE orchestration!")

if __name__ == "__main__":
    run_demo()
