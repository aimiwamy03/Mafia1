import { api } from "../api.js";

const SEATS = [
  { name: "You", x: 480, y: 470, you: true },
  { name: "Maya", x: 250, y: 280 },
  { name: "Chris", x: 400, y: 180 },
  { name: "Priya", x: 560, y: 180 },
  { name: "Owen", x: 710, y: 280 },
];

export class ArcadeScene extends Phaser.Scene {
  constructor() {
    super("ArcadeScene");
    this.state = null;
    this.sprites = {};
    this.bubbles = {};
    this.poller = null;
  }

  async create() {
    this.add.rectangle(480, 320, 960, 640, 0x1b1420);
    this.add.ellipse(480, 320, 360, 180, 0x5a3a22).setStrokeStyle(4, 0x2b1a10);
    this.add.text(480, 40, "ARCADE — WEREWOLF TABLE", {
      fontFamily: "Courier New",
      fontSize: "18px",
      color: "#f4e7c8",
    }).setOrigin(0.5);
    this.status = this.add.text(480, 70, "Starting a round...", {
      fontFamily: "Courier New",
      fontSize: "13px",
      color: "#e6c27a",
    }).setOrigin(0.5);
    this.add.text(480, 610, "Click an NPC to vote them out. ESC returns to town.", {
      fontFamily: "Courier New",
      fontSize: "13px",
      color: "#d8c48a",
    }).setOrigin(0.5);

    SEATS.forEach((seat) => {
      const color = seat.you ? 0xf2d38a : 0x8ec5e8;
      const body = this.add.rectangle(seat.x, seat.y, 36, 42, color).setStrokeStyle(3, 0x111);
      const label = this.add.text(seat.x, seat.y + 32, seat.name, {
        fontFamily: "Courier New",
        fontSize: "12px",
        color: "#f4e7c8",
      }).setOrigin(0.5);
      const bubble = this.add.text(seat.x, seat.y - 50, "", {
        fontFamily: "Courier New",
        fontSize: "11px",
        color: "#1b1a17",
        backgroundColor: "#f4e7c8",
        wordWrap: { width: 160 },
        padding: { x: 6, y: 4 },
      }).setOrigin(0.5).setVisible(false);
      if (!seat.you) {
        body.setInteractive({ useHandCursor: true });
        body.on("pointerdown", () => this.castVote(seat.name));
      }
      this.sprites[seat.name] = { body, label };
      this.bubbles[seat.name] = bubble;
    });

    this.input.keyboard.on("keydown-ESC", () => {
      this.shutdownPoll();
      this.scene.start("TownScene");
    });

    try {
      this.state = await api.startGame();
      this.renderState();
    } catch (err) {
      this.status.setText(err.message);
    }
    this.poller = this.time.addEvent({
      delay: 2000,
      loop: true,
      callback: () => this.refresh(),
    });
  }

  shutdownPoll() {
    if (this.poller) {
      this.poller.remove(false);
      this.poller = null;
    }
  }

  async refresh() {
    try {
      this.state = await api.gameState();
      this.renderState();
    } catch (err) {
      this.status.setText(err.message);
    }
  }

  latestLine(name) {
    const lines = (this.state?.chat || []).filter((line) => line.startsWith(`${name}:`));
    if (!lines.length) return "";
    return lines[lines.length - 1].slice(name.length + 1).trim();
  }

  renderState() {
    const s = this.state;
    if (!s) return;
    const note = s.busy ? s.busy_note || "Thinking..." : `Day ${s.day_number} — ${s.phase.replaceAll("_", " ")}`;
    this.status.setText(s.winner ? `Game over — ${s.winner} win` : note);
    (s.players || []).forEach((p) => {
      const spr = this.sprites[p.name];
      if (!spr) return;
      spr.body.setAlpha(p.alive ? 1 : 0.28);
      const role = p.role ? ` (${p.role})` : "";
      spr.label.setText(p.alive ? p.name + role : `${p.name} ✕`);
      const text = this.latestLine(p.name);
      const bubble = this.bubbles[p.name];
      if (text) {
        bubble.setText(text.slice(0, 90));
        bubble.setVisible(true);
      }
    });
  }

  async castVote(target) {
    if (!this.state || this.state.busy || this.state.winner) return;
    this.status.setText(`You vote for ${target}...`);
    try {
      this.state = await api.vote(target);
      this.renderState();
    } catch (err) {
      this.status.setText(err.message);
    }
  }
}
