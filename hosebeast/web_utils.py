import reflex as rx
from typing import Any


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
