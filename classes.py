# classes.py

class BaseAgent:
    """Eine Basisklasse, die die Grundstruktur für alle Agenten definiert."""
    def __init__(self, name: str, persona: str, client):
        self.name = name
        self.persona = persona
        self.client = client

    def execute(self, task: str, context: str = "") -> str:
        """Die Kernmethode, die von spezialisierten Agenten überschrieben wird."""
        raise NotImplementedError("Die 'execute'-Methode muss von einer Subklasse implementiert werden.")


class TechnologyAgent(BaseAgent):
    """Ein Agent, der auf die Recherche von Technologischen Trends spezialisiert ist."""

    def __init__(self, client=None):
        name = "Technology Expert"
        persona = "Du bist ein erfahrener Technologie-Analyst. Du recherchierst nur Informationen zu technologischen Trends"
        
        # Use global client if none provided
        if client is None:
            try:
                import __main__
                client = __main__.client
            except AttributeError:
                raise ValueError("No client provided and no global 'client' found. Please pass a client parameter.")
        
        super().__init__(name, persona, client)
        self.description = f"Dieser Agent heisst: {self.name.lower()}. Er kann recherchieren und Informationen zu technologischen Trends sammeln."

    def get_description(self):
        """Returns the agent's description."""
        return self.description

    def execute(self, task: str) -> str:
        print(f"INFO: {self.name} führt Recherche für '{task}' aus...")
        from helpers import call_openai, model
        system_prompt = self.persona
        user_prompt = f"Recherchiere das folgende Thema aus deiner Perspektive: {task}"
        response = call_openai(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt
        )
        return response


class MarketAnalysis(BaseAgent):
    """Ein Agent, der die Markt-Dynamiken recherchiert"""

    def __init__(self, client=None):
        name = "Market Analyst"
        persona = "Du bist ein erfahrener Markt-Analyst. Du recherchierst nur Informationen zu Marktdynamiken und wie sich ein Markt entwickelt"
        
        # Use global client if none provided
        if client is None:
            try:
                import __main__
                client = __main__.client
            except AttributeError:
                raise ValueError("No client provided and no global 'client' found. Please pass a client parameter.")
        
        super().__init__(name, persona, client)
        self.description = f"Dieser Agent heisst: {self.name.lower()}. Er kann informationen zu Market Trends recherchieren"

    def get_description(self):
        """Returns the agent's description."""
        return self.description

    def execute(self, text: str) -> str:
        print(f"INFO: {self.name} übersetzt und fasst den Text zusammen...")
        from helpers import call_openai, model
        system_prompt = self.persona
        user_prompt = f"Recherchiere das folgende Thema aus deiner Perspektive:\n\n{text}"
        response = call_openai(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt
        )
        return response


class RegulationAgent(BaseAgent):
    """Ein Agent, der Regulationen in der Schweiz recherchiert"""

    def __init__(self, client=None):
        name = "Regulation Expert"
        persona = "Du bist ein erfahrener Regulationen-Spezialist. Du sammelst nur Informationen zu Regulationen zu einem Thema in der Schweiz."
        
        # Use global client if none provided
        if client is None:
            try:
                import __main__
                client = __main__.client
            except AttributeError:
                raise ValueError("No client provided and no global 'client' found. Please pass a client parameter.")
        
        super().__init__(name, persona, client)
        self.description = f"Dieser Agent heisst: {self.name.lower()}. Er kann Informationen zu aktuellen Schweizer Regulationen sammeln."

    def get_description(self):
        """Returns the agent's description."""
        return self.description

    def execute(self, text: str) -> str:
        print(f"INFO: {self.name} überprüft die Fakten...")
        from helpers import call_openai, model
        system_prompt = self.persona
        user_prompt = f"Recherchiere zum folgenden Thema aus deiner Perspektive:\n\n{text}"
        response = call_openai(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt
        )
        return response


class SummaryAgent:
    def __init__(self, client=None):
        # Use global client if none provided
        if client is None:
            try:
                import __main__
                client = __main__.client
            except AttributeError:
                raise ValueError("No client provided and no global 'client' found. Please pass a client parameter.")
        
        self.client = client

    def run(self, text, inputs):
        combined_prompt = (
            f"The user asked: '{text}'\n\n"
            f"Here are the expert responses:\n"
            f"- Policy Expert: {inputs['policy']}\n\n"
            f"- Technology Expert: {inputs['tech']}\n\n"
            f"- Market Expert: {inputs['market']}\n\n"
            "Please summarize the combined insights into a single clear and concise response."
        )
        print(f"Summary Agent resolving prompt: {combined_prompt}")

        response = self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an energy strategist skilled at synthesizing expert insights."},
                {"role": "user", "content": combined_prompt}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content