"""Welcome to Reflex!."""

# Import all the pages.
# Ignore the unused imports here; they have template side effects
# that add them to the app
from .pages import index, about, profile, settings, table  # noqa: F401
from .templates import template
from . import styles

from .relay_control import set_relay, RELAY_1, RELAY_2
import reflex as rx

from typing import Any

# Create the app.
app = rx.App(
    style=styles.base_style,
    stylesheets=styles.base_stylesheets,
    title="Dashboard Template",
    description="A dashboard template for Reflex.",
)


class HosebeastState(rx.State):
    """The app state."""

    relay_1_off: bool = True
    relay_2_off: bool = True

    adc_gain: float = 1.0
    adc_voltage: float = 2.5
    adc_raw: int = 16000

    async def toggle_relay_1(self):
        self.relay_1_off = not self.relay_1_off
        set_relay(RELAY_1, self.relay_1_off)

    async def toggle_relay_2(self):
        self.relay_2_off = not self.relay_2_off
        set_relay(RELAY_2, self.relay_2_off)


@template(route="/hosebeast", title="Hosebeast")
def hosebeast_layout() -> rx.Component:
    """The main layout of the app."""
    return rx.vstack(
        rx.heading("Hosebeast, Eh", size="2xl"),
        red_green_button(
            "Turn On Relay 1",
            "Turn Off Relay 1",
            var_conditional=HosebeastState.relay_1_off,
            action=HosebeastState.toggle_relay_1,
        ),
        red_green_button(
            "Turn On Relay 2",
            "Turn Off Relay 2",
            var_conditional=HosebeastState.relay_2_off,
            action=HosebeastState.toggle_relay_2,
        ),
    )


def red_green_button(
    true_label: str,
    false_label: str,
    var_conditional: Any,
    action: Any,
    false_action: Any | None = None,
    **props,
) -> rx.cond:
    false_action = false_action or action
    # Return a green and shows one label when var_conditional is True,
    # or red and shows false_label otherwise.
    # If false_action is not specified, call action for both conditions
    return rx.cond(
        var_conditional,
        rx.button(true_label, on_click=action, color_scheme="green", **props),
        rx.button(false_label, on_click=false_action, color_scheme="red", **props),
    )
