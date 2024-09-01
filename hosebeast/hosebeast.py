"""Welcome to Reflex!."""

# Import all the pages.
# Ignore the unused imports here; they have template side effects
# that add them to the app
import reflex as rx
import asyncio
import math
import time

from datetime import datetime, timedelta

from . import styles
from .relay_control import set_relay, RELAY_1, RELAY_2
from .pressure_estimator import (
    get_adc_channel,
    SomeADCWrapper,
    MockADCWrapper,  # noqa: F401
    ADCWrapper,  # noqa: F401
)
from .web_utils import red_green_button


from sqlite_utils import Database

DB = Database("hosebeast.db")

VALID_TIME_RANGES = ["day", "week", "month", "all"]

VALID_TIME_UNITS = ["minutes", "hours", "days"]

SENSOR: SomeADCWrapper = get_adc_channel(0, gain=1.0)


class HBState(rx.State):
    """The app state."""

    relay_1_off: bool = True
    relay_2_off: bool = True

    adc_gain: str = "1"
    adc_voltage: float = 2.512
    adc_raw: int = 16000

    time_range: str = "week"  # one of VALID_TIME_RANGES
    depth_data: list[dict[str, float]] = []

    # Pump scheduling
    p1_start_time: str = "4:30"
    p1_duration_mins: int = 15
    p1_repeat_interval: int = 1
    p1_repeat_units: str = "days"  # from VALID_TIME_UNITS

    # Backend-only vars
    _update_secs: int = 2
    _update_is_running: bool = False
    _db_update_secs: int = 60
    _last_db_time: float = 0

    _depth_slope: float = 0.0001
    _depth_intercept: float = -2

    async def toggle_relay_1(self):
        self.relay_1_off = not self.relay_1_off
        set_relay(RELAY_1, self.relay_1_off)

    async def toggle_relay_2(self):
        self.relay_2_off = not self.relay_2_off
        set_relay(RELAY_2, self.relay_2_off)

    def set_time_range(self, time_range: str):
        if time_range not in VALID_TIME_RANGES:
            raise ValueError(
                f"Invalid time range: {time_range}; must be one of {VALID_TIME_RANGES}"
            )
        self.time_range = time_range
        self.update_depth_data()

    def update_depth_data(self):
        # If we change the time range, we should reload the data
        self.depth_data = self.load_water_depth_data()

    @rx.var
    def water_depth(self) -> float:
        depth = self.adc_raw * self._depth_slope + self._depth_intercept
        return round(depth, 1)

    async def handle_calibration_submit(self, form_dict: dict):
        try:
            # Only calibrate if we have a valid float depth
            actual_depth = float(form_dict["actual_depth"])
            await self.calibrate_depth(actual_depth)
        except ValueError:
            print(f'Invalid depth: {form_dict["actual_depth"]}')
            return

    async def average_raw_and_depths(
        self, measurements=10, interval_s=1
    ) -> tuple[int, float]:
        measurements = int(max(measurements, 1))
        total = 0
        total_depth = 0
        # average several readings before we record
        for i in range(measurements):
            total += self.adc_raw
            total_depth += self.water_depth
            await asyncio.sleep(1)
        mean_raw = int(total / measurements)
        mean_depth = float(total_depth / measurements)
        mean_depth = round(mean_depth, 1)
        return (mean_raw, mean_depth)

    async def calibrate_depth(self, actual_depth: float):
        # TODO: Given a set of known depths and pressures, calculate the slope and intercept
        # of the line that best fits the data.
        # We should probably just store the data in the database and
        # take a linear regression of the data to get the slope and intercept.

        # 1. Store actual_depth and adc_raw in the database
        # 2. Take a linear regression of all the data points to get the slope and intercept
        # 3. Store the slope and intercept in the database
        # 4. Use the slope and intercept to calculate the depth

        mean_raw, mean_depth = await self.average_raw_and_depths()

        # Store actual_depth and adc_raw in the database
        adc_gain = float(self.adc_gain)
        now_minute = even_minute()
        DB["calibration_points"].insert(
            {
                "timestamp": now_minute.timestamp(),
                "datetime": now_minute.isoformat(),
                "adc_raw": mean_raw,
                "actual_depth": actual_depth,
                "adc_gain": adc_gain,
            },
            pk="timestamp",
            replace=True,
            alter=True,
        )

        print(
            f"Calibration: {now_minute}: Storing raw value {mean_raw} for depth {actual_depth:.1f} cm"
        )

        # Retrieve all calibration points
        calibration_points = [
            (row["adc_raw"], float(row["actual_depth"]))
            for row in DB["calibration_points"].rows_where("adc_gain = ?", [adc_gain])
        ]

        # Calculate slope and intercept
        self._depth_slope, self._depth_intercept = (
            linear_regression_with_outlier_removal(calibration_points)
        )

        # Store the new slope and intercept in the database
        DB["calibration"].insert(
            {
                "timestamp": now_minute.timestamp(),
                "datetime": now_minute.isoformat(),
                "slope": self._depth_slope,
                "intercept": self._depth_intercept,
                "adc_gain": adc_gain,
            },
            pk="timestamp",
            replace=True,
            alter=True,
        )

    def load_calibration(self):
        # Load the slope and intercept from the most recent database record
        calibration = next(
            DB["calibration"].rows_where(order_by="-timestamp", limit=1), None
        )

        if calibration:
            print(f"Loaded calibration: {calibration}")
            self._depth_slope = calibration["slope"]
            self._depth_intercept = calibration["intercept"]

    def load_water_depth_data(self) -> list[dict]:
        now = datetime.now()
        if "water_depths" not in DB.table_names():
            return []
        earliest_date_query = DB.query(
            "SELECT MIN(timestamp) as earliest_date FROM water_depths"
        )
        start_ts = next(earliest_date_query)["earliest_date"]
        earliest_date = datetime.fromtimestamp(start_ts)

        if self.time_range == "day":
            start_date = now - timedelta(days=1)
        elif self.time_range == "week":
            start_date = now - timedelta(weeks=1)
        elif self.time_range == "month":
            start_date = now - timedelta(days=30)
        else:  # all time
            earliest_date_query = DB.query(
                "SELECT MIN(timestamp) as earliest_date FROM water_depths"
            )
            start_ts = next(earliest_date_query)["earliest_date"]
            start_date = datetime.fromtimestamp(start_ts)

        start_date = max(earliest_date, start_date)
        start_ts = start_date.timestamp()

        # total_seconds = (now - start_date).total_seconds()

        rows_to_fetch = 200
        # NOTE: 2024-08-31: Because this query skips integer-numbered rows,
        # we can only be precise about the number of rows fetched within
        # +/- rows_to_fetch rows. So... don't limit the query to rows_to_fetch
        # rows; that results in missing the most recent data.


        # Count the rows we'd get, in the entire range from start_ts to now,
        # then divide by the number of rows we want to fetch and query for
        # that many rows.
        # NOTE: if we've been adding to the table irregularly, this will
        # skip those gaps, overrepresenting times when we did get data
        # Maybe we really want something like "get one value for each of
        # rows_to_fetch timeslots between start_ts and now, and interpolate 
        # vals if a given timeslot is empty"
        rows_available = DB["water_depths"].count_where("timestamp >= ?", [start_ts])
        interval_rows = max(1, int(rows_available / rows_to_fetch))

        query = """
        SELECT * FROM (
            SELECT *, ROW_NUMBER() OVER (ORDER BY timestamp) AS row_num
            FROM water_depths
            WHERE timestamp >= ?
        ) AS numbered
        WHERE row_num % ? = 0
        ORDER BY timestamp
        """
        # LIMIT ?
        # data = DB.query(query, [start_ts, interval_rows, rows_to_fetch])
        data = DB.query(query, [start_ts, interval_rows])
        # NOTE: I'm not sure why I need to call list() on the returned "data"
        # generator, but if I don't, I get an empty list
        rows = [r for r in list(data)]
        return rows

    def update_adc_gain(self, gain: str):
        self.adc_gain = gain
        SENSOR.gain = 2 / 3 if gain == "2/3" else int(gain)

    async def update_adc_voltage(self):
        self.adc_voltage = round(SENSOR.voltage, 3)
        self.adc_raw = SENSOR.value
        # every minute, we'll store the pressure in the database
        await self.store_adc_state()

    @rx.background
    async def start_adc_updates(self):
        # Make sure this is only called once, or rejects subsequent calls
        async with self:
            if self._update_is_running:
                return
            else:
                self._update_is_running = True

            # Load info data from the database;
            # we only need to do this once
            # self.check_relay_schedule()
            self.load_schedule_from_db()
            self.load_calibration()
            self.update_depth_data()
            yield HBState.check_relay_schedule()

        while True:
            async with self:
                await self.update_adc_voltage()
            await asyncio.sleep(self._update_secs)

    @rx.background
    async def check_relay_schedule(self):
        while True:
            async with self:
                now = datetime.now()
                next_start, next_end = calculate_next_relay_times(
                    self.p1_start_time,
                    self.p1_duration_mins,
                    self.p1_repeat_interval,
                    self.p1_repeat_units,
                )
                # print(
                #     f"{now}: Checking for relay schedules for range ({next_start}, {next_end})"
                # )

                if next_start <= now < next_end:
                    print(
                        f"{now}: Inside a pump-on region: ({next_start}, {next_end}); turning on"
                    )

                    if self.relay_1_off:
                        await self.toggle_relay_1()
                elif not self.relay_1_off:
                    print(
                        f"{now}: Outside region  ({next_start}, {next_end}); turning off"
                    )
                    await self.toggle_relay_1()
            # Sleep until the top of the next minute
            until_next_minute = even_minute() + timedelta(seconds=60) - now
            await asyncio.sleep(until_next_minute.total_seconds())  # Check every minute

    async def store_adc_state(self):
        now = time.time()
        # if we've already stored the data in the last self._db_update_secs
        # seconds, just return
        if now < self._last_db_time + self._db_update_secs:
            return

        mean_raw, mean_depth = await self.average_raw_and_depths()
        # We can't go below 0
        mean_depth = max(0, mean_depth)
        # We haven't stored the data in the last self._db_update_secs seconds,
        # so store it now
        self._last_db_time = now
        # NOTE: if we start storing differently than once a minute,
        # we might need to adjust the datetime we set here
        now_minute = even_minute()
        row = {
            "timestamp": now_minute.timestamp(),
            "datetime": now_minute.isoformat(),
            "raw_value": mean_raw,
            "water_depth": mean_depth,
        }
        print(f"Storing ADC state: {row}")
        DB["water_depths"].insert(row, pk="timestamp", replace=True)
        # Every time we store data, let's reload the graph data, too
        self.update_depth_data()

    # ===================
    # = pump scheduling =
    # ===================
    def set_p1_start_time(self, val: str):
        # val should be hh:mm, with integers on either side
        # of the colon. If we don't match those, just ignore
        try:
            h, m = (int(v) for v in val.split(":"))
            self.p1_start_time = val
            self.store_schedule()
        except ValueError:
            pass

    # in case of bad data, just ignore; usually good data
    # is typed immediately afterwards
    def set_p1_duration_mins(self, val: str):
        try:
            self.p1_duration_mins = int(val)
            self.store_schedule()
        except ValueError:
            pass

    def set_p1_repeat_interval(self, val: str):
        # in case of bad data, just ignore; usually good data
        # is typed immediately afterwards
        try:
            self.p1_repeat_interval = int(val)
            self.store_schedule()
        except ValueError:
            pass

    def set_p1_repeat_units(self, val: str):
        self.p1_repeat_units = val
        self.store_schedule()

    @rx.var
    def next_relay_1_times(self) -> tuple[str, str]:
        next_start, next_end = calculate_next_relay_times(
            self.p1_start_time,
            self.p1_duration_mins,
            self.p1_repeat_interval,
            self.p1_repeat_units,
        )
        return (
            next_start.strftime("%Y-%m-%d %H:%M:%S"),
            next_end.strftime("%Y-%m-%d %H:%M:%S"),
        )

    def load_schedule_from_db(self):
        if "schedules" not in DB.table_names():
            return
        schedule = DB["schedules"].get(1)  # Assuming we use id=1 for the first schedule
        if schedule:
            self.p1_start_time = schedule["start_time"]
            self.p1_duration_mins = schedule["duration_mins"]
            self.p1_repeat_interval = schedule["repeat_interval"]
            self.p1_repeat_units = schedule["repeat_units"]

    def store_schedule(self):
        DB["schedules"].upsert(
            {
                "id": 1,
                "start_time": self.p1_start_time,
                "duration_mins": self.p1_duration_mins,
                "repeat_interval": self.p1_repeat_interval,
                "repeat_units": self.p1_repeat_units,
            },
            pk="id",
        )

    def update_schedule(
        self,
        start_time: str,
        duration_mins: int,
        repeat_interval: int,
        repeat_units: str,
    ):
        self.p1_start_time = start_time
        self.p1_duration_mins = duration_mins
        self.p1_repeat_interval = repeat_interval
        self.p1_repeat_units = repeat_units
        self.store_schedule()()


# ===========
# = HELPERS =
# ===========
def linear_regression_with_outlier_removal(
    points: list[tuple[float, float]], std_dev_threshold: float = 2.0
) -> tuple[float, float]:
    """
    Perform linear regression on a list of (x, y) points, removing outliers.

    Args:
        points: A list of tuples, where each tuple contains (x, y) coordinates.
        std_dev_threshold: Number of standard deviations to use as threshold for outlier removal.

    Returns:
        A tuple containing (slope, intercept) of the best-fit line after outlier removal.
    """

    def calculate_regression(pts: list[tuple[float, float]]) -> tuple[float, float]:
        n = len(pts)
        sum_x = sum(x for x, _ in pts)
        sum_y = sum(y for _, y in pts)
        sum_xy = sum(x * y for x, y in pts)
        sum_xx = sum(x * x for x, _ in pts)
        denom = n * sum_xx - sum_x * sum_x
        # avoid divide by zero
        if n == 0 or denom == 0:
            return (0, 0)
        slope = (n * sum_xy - sum_x * sum_y) / denom
        intercept = (sum_y - slope * sum_x) / n
        return slope, intercept

    # Initial regression
    slope, intercept = calculate_regression(points)

    # Calculate residuals
    residuals = [(y - (slope * x + intercept)) for x, y in points]

    # Calculate standard deviation of residuals
    mean_residual = sum(residuals) / len(residuals)
    std_dev_residual = math.sqrt(
        sum((r - mean_residual) ** 2 for r in residuals) / len(residuals)
    )

    # Remove outliers
    filtered_points = [
        point
        for point, residual in zip(points, residuals)
        if abs(residual) <= std_dev_threshold * std_dev_residual
    ]

    # Recalculate regression with filtered points
    return calculate_regression(filtered_points)


def calculate_next_relay_times(
    start_time: str, duration_mins: int, repeat_interval: int, repeat_units: str
) -> tuple[datetime, datetime]:
    """
    Given input values defining a range & repeat pattern, tell us the next
    time it will be valid. BUT- if we're currently INSIDE a valid range, return
    that range.
    """
    now = datetime.now()
    today = now.date()
    start_hour, start_minute = (0, 0)
    try:
        # users will often have invalid values in a text field ('4:', '', '3')
        # in the course of entering a date. ignore it if it doesn't work
        start_hour, start_minute = map(int, start_time.split(":"))
    except ValueError:
        pass

    next_start = datetime.combine(
        today, datetime.min.time().replace(hour=start_hour, minute=start_minute)
    )

    while next_start <= now:
        if repeat_units == "minutes":
            next_start += timedelta(minutes=repeat_interval)
        elif repeat_units == "hours":
            next_start += timedelta(hours=repeat_interval)
        elif repeat_units == "days":
            next_start += timedelta(days=repeat_interval)
        elif repeat_units == "weeks":
            next_start += timedelta(weeks=repeat_interval)

        next_end = next_start + timedelta(minutes=duration_mins)
        # if now is between next_start and next_end, we're in a valid
        # range right now; return it
        if next_start <= now <= next_end:
            break

    return next_start, next_end


def delete_db_range(
    start_dt: datetime | None = None,
    end_dt: datetime | None = None,
    table_name: str = "water_depths",
) -> int:
    if start_dt is None:
        start_dt = datetime(2024, 8, 1)
    if end_dt is None:
        end_dt = datetime.now()

    start_ts = start_dt.timestamp()
    end_ts = end_dt.timestamp()

    table = DB[table_name]
    rows_before = table.count
    table.delete_where("timestamp >= ? AND timestamp <= ?", [start_ts, end_ts])
    rows_after = table.count

    return rows_before - rows_after


def even_minute(dt: datetime | None = None) -> datetime:
    dt = dt or datetime.now()
    return dt.replace(second=0, microsecond=0)


# ===============
# = LAYOUT & UI =
# ===============


def hosebeast_layout() -> rx.Component:
    """The main layout of the app."""
    return rx.vstack(
        rx.heading("Hosebeast", size="3xl"),
        rx.hstack(
            red_green_button(
                "Pump 1 On",
                "Pump 1 Off",
                var_conditional=HBState.relay_1_off,
                action=HBState.toggle_relay_1,
            ),
            red_green_button(
                "Pump 2 On",
                "Pump 2 Off",
                var_conditional=HBState.relay_2_off,
                action=HBState.toggle_relay_2,
            ),
        ),
        schedule_interface(),
        rx.vstack(
            # rx.hstack(
            #     rx.text("Gain:"),
            #     rx.select(
            #         ["2/3", "1", "2", "4", "8", "16"],
            #         value=HBState.adc_gain,
            #         default_value="1",
            #         on_change=HBState.update_adc_gain,
            #         width="100%",
            #     ),
            # ),
            rx.hstack(
                rx.text("Depth:", size="5", weight="bold"),
                rx.text(
                    HBState.water_depth.to_string(),
                    " cm",
                    size="5",
                    weight="bold",
                ),
            ),
            rx.hstack(
                rx.text("Raw:"),
                rx.text(HBState.adc_raw, ""),
            ),
            # rx.hstack(
            #     rx.text("Voltage:"),
            #     rx.text(HBState.adc_voltage, " V"),
            # ),
            rx.heading("Water Depth Over Time", size="xl"),
            water_depth_chart(),
            calibration_accordion(),
        ),
        padding_top="2em",
        padding_left="2em",
        on_mount=HBState.start_adc_updates,
    )


def schedule_interface() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.text("Pumps on at "),
            rx.input(
                value=HBState.p1_start_time,
                on_change=HBState.set_p1_start_time,
                width=60,
            ),
            rx.text(" for "),
            rx.input(
                value=HBState.p1_duration_mins,
                on_change=HBState.set_p1_duration_mins,
                width=40,
            ),
            rx.text(" minutes"),
        ),
        rx.hstack(
            rx.text("Every "),
            rx.input(
                value=HBState.p1_repeat_interval,
                on_change=HBState.set_p1_repeat_interval,
                width=40,
            ),
            rx.select(
                VALID_TIME_UNITS,
                value=HBState.p1_repeat_units,
                on_change=HBState.set_p1_repeat_units,
            ),
        ),
        rx.text(f"{HBState.next_relay_1_times[0]} - {HBState.next_relay_1_times[1]}"),
    )


def water_depth_chart() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.button(
                "Day",
                on_click=lambda: HBState.set_time_range("day"),
                box_shadow=rx.cond(
                    HBState.time_range == "day",
                    "0 0 0 4px #3182CE",
                    "none"
                ),
            ),
            rx.button(
                "Week",
                on_click=lambda: HBState.set_time_range("week"),
                box_shadow=rx.cond(
                    HBState.time_range == "week",
                    "0 0 0 4px #3182CE",
                    "none"
                ),
            ),
            rx.button(
                "Month",
                on_click=lambda: HBState.set_time_range("month"),
                box_shadow=rx.cond(
                    HBState.time_range == "month",
                    "0 0 0 4px #3182CE",
                    "none"
                ),
            ),
            rx.button(
                "All Time",
                on_click=lambda: HBState.set_time_range("all"),
                box_shadow=rx.cond(
                    HBState.time_range == "all",
                    "0 0 0 4px #3182CE",
                    "none"
                ),
                            ),
            spacing="4",
        ),
        rx.recharts.line_chart(
            rx.recharts.line(
                data_key="water_depth",
                unit="cm",
                stroke="#3182CE",
                stroke_width=3,
                name="Depth",
                type_="monotone",
                dot=False,
                y_axis_id="right",
            ),
            # FIXME: This looks OK-ish with datetime and "category" type,
            # but the x-axis then gives equal space to each data element, rather
            # than their semantic meaning.
            # (e.g. a graph with points last Sunday & Monday and this Friday
            #  appears equally spaced rather than two points left and one point right)
            # Native React recharts charts get around this by setting type="number",
            # using the data's timestamp as the x-axis value, and applying a
            # custom formatting function (tickFunction) to the x-axis labels.
            # From what I can see, this is not possible in Reflex, because we can't
            # pass a callable for tickFunction.
            rx.recharts.x_axis(data_key="datetime", type_="category", tick_count=2),
            rx.recharts.y_axis(
                data_key="water_depth", orientation="right", y_axis_id="right"
            ),
            # When showing raw values as well as depth values, we put an
            # extra axis on the left. Turned off for now
            # rx.recharts.line(
            #     data_key="raw_value",
            #     stroke="#4884d8",
            #     name="Raw",
            #     type_="monotone",
            #     dot=False,
            #     y_axis_id="left",
            # ),
            # rx.recharts.y_axis(
            #     data_key="raw_value", orientation="left", y_axis_id="left"
            # ),
            rx.recharts.graphing_tooltip(),
            data=HBState.depth_data,
            width=360,
            height=240,
        ),
    )


def calibration_accordion() -> rx.Component:
    return rx.accordion.root(
        rx.accordion.item(
            header="Calibrate",
            content=rx.form.root(
                rx.hstack(
                    rx.input(
                        name="actual_depth",
                        # default_value="search",
                        placeholder="Enter actual depth in cm",
                        # type="password",
                        required=True,
                    ),
                    rx.button("Calibrate", type="submit"),
                    width="100%",
                ),
                on_submit=HBState.handle_calibration_submit,
                reset_on_submit=True,
                width="100%",
            ),
        ),
        collabsible=True,
        variant="ghost",  # 'ghost' is a transparent background
        type="multiple",
        width="100%",
    )

# ===============
# = ENTRY POINT =
# ===============

# Create the app.
app = rx.App(
    style=styles.base_style,
    stylesheets=styles.base_stylesheets,
    title="Hosebeast Irrigation Controller",
    description="Irrigation control system for Raspberry Pi 4",
)
app.add_page(hosebeast_layout(), "/")