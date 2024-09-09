import reflex as rx
from typing import Any
import os


def red_green_button(
    true_label: str,
    false_label: str,
    var_conditional: Any,
    action: Any,
    false_action: Any | None = None,
    **props,
) -> rx.Component:
    false_action = false_action or action
    # Return a green and shows one label when var_conditional is True,
    # or red and shows false_label otherwise.
    # If false_action is not specified, call action for both conditions
    return rx.cond(
        var_conditional,
        rx.button(true_label, on_click=action, color_scheme="green", **props),
        rx.button(false_label, on_click=false_action, color_scheme="red", **props),
    )


def get_bool_from_env(env_var_name: str) -> bool:
    """
    Get a boolean value from an environment variable.

    Args:
        env_var_name (str): The name of the environment variable.

    Returns:
        bool: True if the environment variable is set and not '0' or 'False' (case-insensitive),
              False if undefined or '0' or 'False'
    """
    env_value = os.environ.get(env_var_name, "false")
    return env_value.lower() not in ("0", "false", "f")
