# AuroraWake

> A smart alarm clock that gently guides you into waking up instead of startling you.

AuroraWake is a light and sound alarm clock project designed to make waking up feel more natural. The device gradually adjusts its light intensity and, if necessary, adds a gentle sound at the selected time.

## Goals

- Reduce sudden and unpleasant wake-ups.
- Use gradually increasing light as the primary wake-up signal.
- Keep the experience simple, quiet, and respectful of sleep.
- Design an accessible, repairable, and well-documented device.

## Project structure

```text
AuroraWake/
├── docs/        Documentation, schematics, and design decisions
├── firmware/    Alarm clock embedded software
├── hardware/    Schematics, PCB, and manufacturing files
├── prototypes/  Tests, mockups, and experiments
└── README.md    Project overview
```

## Development status

The project is currently in the electronic design phase. The overall architecture is built around an **ESP32** controller, which will coordinate:

- gradual lighting through a voltage dimmer;
- alarm information on the display;
- the speaker through an audio amplifier;
- the physical buttons and the RTC clock;
- Bluetooth communication with a smartphone application.

The next step is to select suitable components and check their compatibility. The schematic will then be refined before the first prototype is designed.

<div align="center">
	<img src="docs/img/AuroraWake.png" alt="AuroraWake functional architecture" width="500" style="margin: 24px 0;">
</div>

<p align="center"><em>Preliminary functional architecture of AuroraWake.</em></p>

## Author

Project designed and developed by **Bosco**.