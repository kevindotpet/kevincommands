import asyncio
from collections import Counter
from datetime import datetime, timedelta
from twitchio.ext import commands
import requests
import logging
import aiohttp

TWITCH_TOKEN = ""
TWITCH_CLIENT_ID = ""
TWITCH_CHANNEL = "kevindotpet"
XGOBOT_API_URL = ""
STREAMLABS_API_URL = ""
STREAMLABS_ACCESS_TOKEN = ""
LOG_FILE = "kevin_debug.log"

VALID_COMMANDS = [
    "/squat", "/pee", "/sit", "/wave", "/pushup", "/360", "/stretch", "/handshake", "/crawl"
]

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("KevinBot")


class CommandTracker:
    def __init__(self):
        self.command_log = []

    def add_command(self, command):
        self.command_log.append((command, datetime.now()))
        logger.debug(f"Command logged: {command}")

    def get_most_popular_command(self):
        now = datetime.now()
        cutoff = now - timedelta(seconds=30)
        recent_commands = [cmd for cmd, timestamp in self.command_log if timestamp >= cutoff]
        if not recent_commands:
            logger.debug("No commands received in the last 30 seconds.")
            return None
        command_counts = Counter(recent_commands)
        most_popular = command_counts.most_common(1)[0][0]
        logger.info(f"Most popular command: {most_popular} (count: {command_counts[most_popular]})")
        return most_popular

    def cleanup(self):
        now = datetime.now()
        cutoff = now - timedelta(seconds=30)
        original_count = len(self.command_log)
        self.command_log = [(cmd, timestamp) for cmd, timestamp in self.command_log if timestamp >= cutoff]
        logger.debug(f"Cleaned up old commands. Removed {original_count - len(self.command_log)} entries.")


class TwitchBot(commands.Bot):
    def __init__(self):
        super().__init__(token=TWITCH_TOKEN, prefix="!", initial_channels=[TWITCH_CHANNEL])
        self.command_tracker = CommandTracker()

    async def event_ready(self):
        logger.info(f"Bot connected as {self.nick}")

    async def event_message(self, message):
        if message.author.name.lower() == self.nick.lower():
            return
        content = message.content.strip()
        if content in VALID_COMMANDS:
            self.command_tracker.add_command(content)
        else:
            logger.debug(f"Ignored message: {content}")

    async def send_command_to_robot(self):
        while True:
            try:
                most_popular_command = self.command_tracker.get_most_popular_command()
                if most_popular_command:
                    logger.info(f"Sending command to robot: {most_popular_command}")
                    response = requests.post(
                        XGOBOT_API_URL,
                        json={"command": most_popular_command},
                        timeout=5
                    )
                    if response.status_code == 200:
                        logger.info(f"Robot executed command: {most_popular_command}")
                    else:
                        logger.error(f"Failed to send command to robot: {response.status_code} - {response.text}")
                else:
                    logger.info("No commands to send this cycle.")
                self.command_tracker.cleanup()
            except requests.exceptions.RequestException as e:
                logger.error(f"Error communicating with robot: {e}")
            except Exception as e:
                logger.exception(f"Unexpected error: {e}")
            await asyncio.sleep(30)

    async def listen_for_donations(self):
        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    headers = {"Authorization": f"Bearer {STREAMLABS_ACCESS_TOKEN}"}
                    async with session.get(STREAMLABS_API_URL, headers=headers) as response:
                        if response.status == 200:
                            donations = await response.json()
                            if donations.get("donations"):
                                for donation in donations["donations"]:
                                    await self.handle_donation(donation)
                        else:
                            logger.error(f"Failed to fetch donations: {response.status}")
            except Exception as e:
                logger.exception(f"Error listening for donations: {e}")
            await asyncio.sleep(10)

    async def handle_donation(self, donation):
        donor_name = donation.get("name", "Anonymous")
        amount = donation.get("amount", 0)
        message = donation.get("message", "")
        logger.info(f"Donation received from {donor_name}: ${amount} - {message}")

        special_command = "/wave"
        logger.info(f"Sending special command to robot: {special_command} for donation")
        response = requests.post(
            XGOBOT_API_URL,
            json={"command": special_command},
            timeout=5
        )
        if response.status_code == 200:
            logger.info(f"Robot executed special command: {special_command}")
        else:
            logger.error(f"Failed to send special command to robot: {response.status_code} - {response.text}")


if __name__ == "__main__":
    bot = TwitchBot()
    loop = asyncio.get_event_loop()
    loop.create_task(bot.send_command_to_robot())
    loop.create_task(bot.listen_for_donations())
    loop.run_until_complete(bot.run())
