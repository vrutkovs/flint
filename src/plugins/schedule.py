from telega.settings import Settings
from telegram.ext import CallbackContext

class ScheduleData:
    def __init__(self, settings: Settings, genai_client):
        self.settings = settings
        self.genai_client = genai_client


async def send_agenda(context: CallbackContext):
    job = context.job
    if not job:
        return
    job_data = job.data
    if not job_data:
        return
    await context.bot.send_message(chat_id=job.chat_id, text="Agenda")
