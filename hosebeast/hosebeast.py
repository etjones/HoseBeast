"""Welcome to Reflex!."""

# Import all the pages.
# Ignore the unused imports here; they have template side effects
# that add them to the app
import reflex as rx
import asyncio
import math
import time

from datetime import datetime, timedelta

# from .pages import index, about, profile, settings, table  # noqa: F401
from .templates import template
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


# PRESSURE = get_adc_channel(0, 1, gain=1.0)

# Create the app.
app = rx.App(
    style=styles.base_style,
    stylesheets=styles.base_stylesheets,
    title="Dashboard Template",
    description="A dashboard template for Reflex.",
)

VALID_TIME_RANGES = ["day", "week", "month", "all"]

SENSOR: SomeADCWrapper = get_adc_channel(0, gain=1.0)


class HosebeastState(rx.State):
    """The app state."""

    relay_1_off: bool = True
    relay_2_off: bool = True

    adc_gain: str = "1"
    adc_voltage: float = 2.512
    adc_raw: int = 16000

    time_range: str = "day"  # one of VALID_TIME_RANGES
    depth_data: list[dict[str, float]] = []

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
        return round(depth, 2)

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
        now_minute = datetime.now().replace(second=0, microsecond=0)
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
            # ETJ DEBUG
            print(f"Loaded calibration: {calibration}")
            # END DEBUG
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

        rows_to_fetch = 400

        # Count the rows we'd get, in the entire range from start_ts to now,
        # then divide by the number of rows we want to fetch and query for
        # that many rows.
        # NOTE: if we've been adding to the table irregularly, this will
        # skip those gaps, overrepresenting times when we did get data
        # Maybe we really want something like "get one value for each of
        # rows_to_fetch timeslots between start_ts and now, and insert dummy
        # zero vals if a given timeslot is empty"
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
        LIMIT ?
        """
        data = DB.query(query, [start_ts, interval_rows, rows_to_fetch])

        # data = DB.query(query, [start_ts, rows_to_fetch])
        rows = [r for r in list(data)]
        # ETJ DEBUG
        # # print(f"rows = {len(rows)}")
        # print(f"{rows =}")
        # END DEBUG
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

            # Load the calibration data from the database;
            # we only need to do this once
            self.load_calibration()
            self.depth_data = self.load_water_depth_data()

        while True:
            async with self:
                await self.update_adc_voltage()
            await asyncio.sleep(self._update_secs)

    async def store_adc_state(self):
        now = time.time()
        # if we've already stored the data in the last self._db_update_secs
        # seconds, just return
        if now < self._last_db_time + self._db_update_secs:
            return

        mean_raw, mean_depth = await self.average_raw_and_depths()

        # We haven't stored the data in the last self._db_update_secs seconds,
        # so store it now
        self._last_db_time = now
        # NOTE: if we start storing differently than once a minute,
        # we might need to adjust the datetime we set here
        this_minute = datetime.now().replace(second=0, microsecond=0)
        row = {
            "timestamp": this_minute.timestamp(),
            "datetime": this_minute.isoformat(),
            "raw_value": mean_raw,
            "water_depth": mean_depth,
        }
        print(f"Storing ADC state: {row}")
        DB["water_depths"].insert(row, pk="timestamp", replace=True)
        # Every time we store data, let's reload the graph data, too
        self.update_depth_data()


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


# ==========
# = LAYOUT =
# ==========


@template(route="/hosebeast", title="Hosebeast")
def hosebeast_layout() -> rx.Component:
    """The main layout of the app."""
    return rx.vstack(
        rx.heading("Hosebeast", size="2xl"),
        rx.hstack(
            red_green_button(
                "Pump 1 On",
                "Pump 1 Off",
                var_conditional=HosebeastState.relay_1_off,
                action=HosebeastState.toggle_relay_1,
            ),
            red_green_button(
                "Pump 2 On",
                "Pump 2 Off",
                var_conditional=HosebeastState.relay_2_off,
                action=HosebeastState.toggle_relay_2,
            ),
        ),
        rx.vstack(
            # rx.hstack(
            #     rx.text("Gain:"),
            #     rx.select(
            #         ["2/3", "1", "2", "4", "8", "16"],
            #         value=HosebeastState.adc_gain,
            #         default_value="1",
            #         on_change=HosebeastState.update_adc_gain,
            #         width="100%",
            #     ),
            # ),
            rx.hstack(
                rx.text("Depth:", size="5", weight="bold"),
                rx.text(
                    HosebeastState.water_depth.to_string(),
                    " cm",
                    size="5",
                    weight="bold",
                ),
            ),
            rx.hstack(
                rx.text("Raw:"),
                rx.text(HosebeastState.adc_raw, ""),
            ),
            # rx.hstack(
            #     rx.text("Voltage:"),
            #     rx.text(HosebeastState.adc_voltage, " V"),
            # ),
            rx.heading("Water Depth Over Time", size="xl"),
            water_depth_chart(),
            calibration_accordion(),
        ),
        on_mount=HosebeastState.start_adc_updates,
    )


def water_depth_chart() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.button("Day", on_click=lambda: HosebeastState.set_time_range("day")),
            rx.button("Week", on_click=lambda: HosebeastState.set_time_range("week")),
            rx.button("Month", on_click=lambda: HosebeastState.set_time_range("month")),
            rx.button(
                "All Time", on_click=lambda: HosebeastState.set_time_range("all")
            ),
            spacing="4",
        ),
        rx.recharts.line_chart(
            rx.recharts.line(
                data_key="water_depth",
                unit="cm",
                stroke="#8884d8",
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
            # extra axis on the left. turned off for now
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
            data=HosebeastState.depth_data,
            width=400,
            height=400,
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
                on_submit=HosebeastState.handle_calibration_submit,
                reset_on_submit=True,
                width="100%",
            ),
            collabsible=True,
            variant="ghost",  # 'ghost' is a transparent background
        ),
    )
