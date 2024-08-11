"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import reflex as rx

from rxconfig import config
from datetime import datetime, timedelta
from dataclasses import dataclass

@dataclass
class ScheduledEvent:
    name: str
    start: datetime
    duration_minutes: int
    repetition_hours: int

    def __str__(self):
        if repetition_hours == 24:
            repeat_str = 'daily' 
        else:
            repeat_str = f'every {repetition_hours} hours'
        return f'{name}: {start.hour}:{start.minute} for {duration} minutes {repeat_str}'

class State(rx.State):
    """The app state."""
    relay_on: bool
    events: list[ScheduledEvent]


def index() -> rx.Component:
    return rx.container(
        rx.heading('HoseBeast Controls'),
        rx.hstack(
            rx.text('Relay state'),
            rx.cond(
                State.relay_on,
                rx.text('On'),
                rx.text('Off'),
            ),
        ),
        rx.cond(
            State.relay_on,
            rx.text("Turn Off", color="red"),
            rx.text("Turn On", color="green"),
        )
    )

def index_orig() -> rx.Component:
    # Welcome Page (Index)
    return rx.container(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            rx.heading("Welcome to Reflex!", size="9"),
            rx.text(
                "Get started by editing ",
                rx.code(f"{config.app_name}/{config.app_name}.py"),
                size="5",
            ),
            rx.link(
                rx.button("Check out our docs!"),
                href="https://reflex.dev/docs/getting-started/introduction/",
                is_external=True,
            ),
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
        rx.logo(),
    )


app = rx.App()
app.add_page(index)
