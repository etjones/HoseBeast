"""Welcome to Reflex!."""

# Import all the pages.
# Ignore the unused imports here; they have template side effects
# that add them to the app
from .pages import index, about, profile, settings, table  # noqa: F401
from .templates import template
from . import styles

# from . import relay_control
from .relay_control import set_relay, RELAY_1, RELAY_2
import reflex as rx


# Create the app.
app = rx.App(
    style=styles.base_style,
    stylesheets=styles.base_stylesheets,
    title="Dashboard Template",
    description="A dashboard template for Reflex.",
)


class HosebeastState(rx.State):
    """The app state."""

    relay_1_on: bool = False
    relay_2_on: bool = False

    async def toggle_relay_1(self):
        self.relay_1_on = not self.relay_1_on
        # print(f"Relay 1 is now {self.relay_1_on}")
        set_relay(RELAY_1, self.relay_1_on)

    async def toggle_relay_2(self):
        self.relay_2_on = not self.relay_2_on
        # print(f"Relay 2 is now {self.relay_2_on}")
        set_relay(RELAY_2, self.relay_2_on)


@template(route="/hosebeast", title="Hosebeast")
def hosebeast_layout() -> rx.Component:
    """The main layout of the app."""
    return rx.vstack(
        rx.heading("Hosebeast, Eh", size="2xl"),
        rx.text(
            "Get started by editing ",
            rx.code("hosebeast/pages/index.py"),
            ".",
        ),
        rx.cond(
            HosebeastState.relay_1_on,
            rx.button(
                "Turn off Relay 1",
                on_click=HosebeastState.toggle_relay_1,
                color_scheme="red",
                width="100%",
            ),
            rx.button(
                "Turn on Relay 1",
                on_click=HosebeastState.toggle_relay_1,
                color_scheme="green",
                width="100%",
            ),
        ),
        rx.cond(
            HosebeastState.relay_2_on,
            rx.button(
                "Turn off Relay 2",
                on_click=HosebeastState.toggle_relay_2,
                color_scheme="red",
                width="100%",
            ),
            rx.button(
                "Turn on Relay 2",
                on_click=HosebeastState.toggle_relay_2,
                color_scheme="green",
                width="100%",
            ),
        ),
    )
