import argparse
import asyncio
import logging
from json import JSONDecodeError
from typing import Optional

import aiohttp as aiohttp
from aiohttp.client_exceptions import ClientConnectorError
from pydantic.error_wrappers import ValidationError
from pydantic.main import BaseModel
from pydantic.tools import parse_obj_as

LOG = logging.getLogger(__name__)


class SensorReading(BaseModel):
    temp: float
    humidity: float
    temps: list[float]

    def __str__(self):
        direction = self.temps[-1] - self.temps[0]
        if direction > 0:
            direction_char = "↗"
        else:
            direction_char = "↘"
        return f"{round(self.temp)}f{direction_char} {round(self.humidity)}%"


def format_jsondecodeerror(error: JSONDecodeError, left_pad: int = 5) -> str:
    """
    formats a JSONDecodeError into a string which can be printed, pointing to the error in the raw JSON
    Args:
        error: the error to format
        left_pad: how much of the JSON with which to lead into the "error point"

    Returns:
        a string which can be printed to show where in the JSON the error takes place
    """
    out = str(error)
    out += "\n"
    out += " " * max(0, left_pad - error.pos)
    out += repr(
        error.doc[max(error.pos - left_pad, 0) : min(error.pos + 100, len(error.doc))]
    )
    out += "\n"
    out += " " * (left_pad + 1) + "^"
    return out


async def request_sensor(url: str) -> Optional[SensorReading]:
    """
    retrieves a reading from the ESP32 weather station
    Args:
        url: where to find the JSON encoded sensor readings

    Returns:
        SensorReading object, or None if an error ocurred
    """
    async with aiohttp.ClientSession() as session:
        try:
            response = await session.get(url)
        except ClientConnectorError as e:
            LOG.error(e)
            return None

        async with response:
            try:
                json = await response.json(content_type=None)
            except JSONDecodeError as e:
                LOG.error(format_jsondecodeerror(e))
                return None

            try:
                sensor_reading = parse_obj_as(SensorReading, json)
            except ValidationError as e:
                LOG.error(e)
                return None
            return sensor_reading


async def main(args: argparse.Namespace):
    sensor_reading = await request_sensor(args.url)
    if sensor_reading is None:
        return 1
    print(sensor_reading)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Default async python template",
    )
    parser.add_argument(
        "-u", "--url", help="url to request", default="http://esp32.lan/inline"
    )
    args = parser.parse_args()
    exit(asyncio.run(main(args)))
