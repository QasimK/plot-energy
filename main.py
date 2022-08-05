#!./venv/bin/python
import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import wraps
from typing import Literal
from urllib.request import Request, urlopen

import plotly.graph_objects as go
from plotly.subplots import make_subplots

GAS_M3_TO_KWH = 11.3627


def interpolate(first: float, second: float, current: float, data_first: float, data_second: float) -> float:
    progress = (current - first) / (second - first)
    return data_first + (data_second - data_first) * progress


def ts(day: date) -> int:
    return int(datetime(day.year, day.month, day.day, 0, 0, 0).timestamp())


def as_list(func):
    @wraps(func)
    def inner(*args, **kwargs):
        return list(func(*args, **kwargs))
    return inner


@dataclass(frozen=True)
class Reading:
    at: date
    electricity: int
    gas: float

    def get(self, energy: Literal["electricity", "gas"]) -> float:
        return getattr(self, energy)


@dataclass(frozen=True)
class Weather:
    at: date
    air_mean: float


@dataclass(frozen=True)
class Data:
    readings: list[Reading]
    weathers: list[Weather]

    def reading(self, at: date, energy: Literal["electricity", "gas"]) -> float:
        assert self.readings[0].at <= at <= self.readings[-1].at

        if at == self.readings[0].at:
            return self.readings[0].get(energy)

        second_reading = next(reading for reading in self.readings if at <= reading.at)
        first_reading = self.readings[self.readings.index(second_reading) - 1]

        return interpolate(
            ts(first_reading.at),
            ts(second_reading.at),
            ts(at),
            first_reading.get(energy),
            second_reading.get(energy),
        )

    def usage(self, at: date, energy: Literal["electricity", "gas"]) -> float:
        assert self.readings[0].at < at <= self.readings[-1].at
        return self.reading(at, energy) - self.reading(at - timedelta(days=1), energy)

    def electricity_reading(self, at: date) -> float:
        return self.reading(at, "electricity")

    def electricity_usage(self, at: date) -> float:
        return self.usage(at, "electricity")

    def gas_reading(self, at: date) -> float:
        return self.reading(at, "gas")

    def gas_usage(self, at: date) -> float:
        return self.usage(at, "gas")

    @property
    def average_annual_electricity_consumption(self):
        start = self.usage_dates[0]
        end = start + timedelta(days=365)

        electricity_start = self.electricity_reading(start)
        electricity_end = self.electricity_reading(end)

        return electricity_end - electricity_start

    @property
    def average_annual_gas_consumption(self):
        start = self.usage_dates[0]
        end = start + timedelta(days=365)

        gas_start = self.gas_reading(start)
        gas_end = self.gas_reading(end)

        return gas_end - gas_start

    @property
    @as_list
    def dates(self) -> list[date]:
        day = self.readings[0].at + timedelta(days=1)
        while day <= self.readings[-1].at:
            yield day
            day += timedelta(days=1)

    @property
    def usage_dates(self) -> list[date]:
        return self.dates[1:]

    @property
    @as_list
    def electricity_usages(self) -> list[float]:
        for day in self.usage_dates:
            yield self.electricity_usage(day)

    @property
    @as_list
    def gas_usages(self) -> list[float]:
        for day in self.usage_dates:
            yield self.gas_usage(day)

    @property
    @as_list
    def temperature_dates(self) -> list[date]:
        for weather in self.weathers:
            if self.readings[0].at <= weather.at <= self.readings[-1].at:
                yield weather.at

    @property
    @as_list
    def air_means(self) -> list[float]:
        for weather in self.weathers:
            if self.readings[0].at <= weather.at <= self.readings[-1].at:
                yield weather.air_mean


readings = []
with open("data.tsv") as fin:
    reader = csv.reader(fin, delimiter="\t")
    for date_str, elec_str, gas_str in reader:
        readings.append(Reading(
            datetime.strptime(date_str, "%Y-%m-%d").date(),
            int(elec_str),
            float(gas_str) * GAS_M3_TO_KWH,
        ))

request = Request(
    url="https://www.metoffice.gov.uk/pub/data/weather/uk/climate/stationdata/heathrowdata.txt",
    headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:99.0) Gecko/20100101 Firefox/99.0"},
)
with urlopen(request) as fin:
    temps_raw = fin.read().decode("utf-8").split("\r\n")[7:]

weathers = []
for temp_raw in temps_raw:
    year_str, month_str, tmax_str, tmin_str, air_frost_str, rain_mm_str, sun_hrs_str, *extra = temp_raw.split()
    day = date(int(year_str), int(month_str), 15)
    air_mean = (float(tmin_str) + float(tmax_str)) / 2
    weathers.append(Weather(day, air_mean))

data = Data(readings, weathers)

try:
    print(f"Average Annual Electricity Consumption: {data.average_annual_electricity_consumption:.0f} kWh")
    print(f"Average Annual Gas Consumption: {data.average_annual_gas_consumption:.0f} kWh")
except AssertionError:
    print("Insufficient data for annual consumption data.")


fig = make_subplots(specs=[[{"secondary_y": True}]])
fig.add_trace(go.Scatter(x=data.usage_dates, y=data.electricity_usages, name="Electricity", line_shape="spline"))
fig.add_trace(go.Scatter(x=data.usage_dates, y=data.gas_usages, name="Gas", line_shape="spline"))
fig.add_trace(go.Scatter(x=data.temperature_dates, y=data.air_means, name="Temperature", line_shape="spline"), secondary_y=True)

fig.update_xaxes(title_text="Date (Middle of Month)", dtick="M1", tick0="2000-01-15", tickformat="%b %Y")
fig.update_yaxes(title_text="Consumption (kWh)", rangemode="tozero")
fig.update_yaxes(title_text="Air Temperature (°C)", rangemode="tozero", secondary_y=True)
fig.show()
