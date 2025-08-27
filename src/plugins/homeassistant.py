from homeassistant_api import Client


class HomeAssistant:
    def __init__(self, ha_url, ha_token, logger, timezone):
        self.client = Client(ha_url, ha_token)
        self.logger = logger
        self.timezone = timezone

    def get_weather_forecast(self, entity_id):
        weather = self.client.get_domain("weather")
        if weather is None:
            raise ValueError("Failed to get weather domain")
        _, data = weather.get_forecasts(
            entity_id=entity_id,
            type="hourly",
        )  # pyright: ignore
        self.logger.info(f"Received weather forecast for entity {entity_id}:\n{data}")
        return data
