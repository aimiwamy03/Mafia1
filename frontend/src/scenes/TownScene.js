import { api } from "../api.js";

const BUILDINGS = [
  { id: "photo", label: "PHOTO", x: 196, y: 132, w: 226, h: 178, doorY: 210 },
  { id: "post", label: "POST", x: 745, y: 145, w: 220, h: 166, doorY: 248 },
  { id: "bank", label: "BANK", x: 187, y: 493, w: 190, h: 147, doorY: 555 },
  { id: "library", label: "LIBRARY", x: 738, y: 503, w: 220, h: 177, doorY: 585 },
  { id: "arcade", label: "ARCADE", x: 480, y: 555, w: 255, h: 142, doorY: 595 },
];

const NPCS = [
  { name: "Luna", x: 350, y: 286, tint: 0xffc2d2, bounds: [285, 250, 438, 385] },
  { name: "Rowan", x: 570, y: 286, tint: 0xb9dcff, bounds: [520, 250, 635, 385] },
  { name: "Tavi", x: 310, y: 402, tint: 0xffe0a8, bounds: [250, 365, 440, 450] },
  { name: "Nia", x: 650, y: 360, tint: 0xc9f3c2, bounds: [610, 270, 860, 405] },
  { name: "Sol", x: 520, y: 420, tint: 0xe0c3ff, bounds: [455, 380, 610, 455] },
  { name: "Miko", x: 820, y: 340, tint: 0xffc98d, bounds: [780, 275, 900, 405] },
];

export class TownScene extends Phaser.Scene {
  constructor() {
    super("TownScene");
    this.near = null;
    this.busy = false;
  }

  create() {
    this.add.image(480, 320, "town").setDepth(-10);
    this.buildings = this.physics.add.staticGroup();
    this.doors = [];

    BUILDINGS.forEach((b) => {
      const rect = this.add.rectangle(b.x, b.y, b.w, b.h, 0x000000, 0);
      this.physics.add.existing(rect, true);
      this.buildings.add(rect);
      this.add.text(b.x, b.y - b.h / 2 - 15, b.label, {
        fontFamily: "Courier New",
        fontSize: "14px",
        color: "#f4e7c8",
      }).setOrigin(0.5);
      const door = this.add.rectangle(b.x, b.doorY, 38, 22, 0x1b1a17, 0);
      this.physics.add.existing(door, true);
      door.storeId = b.id;
      this.doors.push(door);
    });

    this.add.text(480, 300, "TOWN SQUARE", {
      fontFamily: "Courier New",
      fontSize: "16px",
      color: "#d8c48a",
    }).setOrigin(0.5);

    this.player = this.add.image(480, 320, "player");
    this.physics.add.existing(this.player);
    this.player.body.setSize(20, 28);
    this.player.setDepth(2);
    this.player.body.setCollideWorldBounds(true);
    this.physics.add.collider(this.player, this.buildings);
    this.createNPCs();

    this.cursors = this.input.keyboard.createCursorKeys();
    this.wasd = this.input.keyboard.addKeys("W,A,S,D,E");
    this.hint = this.add.text(480, 610, "Walk to a doorway and press E", {
      fontFamily: "Courier New",
      fontSize: "14px",
      color: "#f4e7c8",
    }).setOrigin(0.5);

    document.getElementById("panel-close").onclick = () => this.closePanel();
  }

  preload() {
    this.load.svg("town", "/assets/town.svg", { width: 960, height: 640 });
    this.load.svg("player", "/assets/player.svg", { width: 32, height: 40 });
    this.load.svg("npc-front", "/assets/npc-front.svg", { width: 32, height: 44 });
    this.load.svg("npc-back", "/assets/npc-back.svg", { width: 32, height: 44 });
    this.load.svg("npc-side", "/assets/npc-side.svg", { width: 32, height: 44 });
  }

  createNPCs() {
    this.npcs = NPCS.map((config, index) => {
      const shadow = this.add.ellipse(config.x, config.y + 18, 25, 8, 0x23483e, 0.35);
      shadow.setDepth(config.y - 1);
      const sprite = this.add.image(config.x, config.y - 14, "npc-front");
      sprite.setTint(config.tint);
      sprite.setDepth(config.y + 10);
      const name = this.add.text(config.x, config.y - 47, config.name, {
        fontFamily: "Courier New",
        fontSize: "10px",
        color: "#f4e7c8",
        stroke: "#29483f",
        strokeThickness: 3,
      }).setOrigin(0.5).setDepth(config.y + 11);
      return {
        ...config,
        sprite,
        shadow,
        nameLabel: name,
        vx: index % 2 ? -1 : 1,
        vy: 0,
        nextTurn: 0,
        phase: index * 0.8,
      };
    });
  }

  updateNPCs(time, delta) {
    const seconds = delta / 1000;
    this.npcs.forEach((npc) => {
      if (time > npc.nextTurn) {
        const angle = Phaser.Math.FloatBetween(0, Math.PI * 2);
        npc.vx = Math.cos(angle);
        npc.vy = Math.sin(angle);
        npc.nextTurn = time + Phaser.Math.Between(900, 2600);
      }
      const speed = 23;
      const nextX = npc.x + npc.vx * speed * seconds;
      const nextY = npc.y + npc.vy * speed * seconds;
      if (this.npcBlocked(npc, nextX, nextY)) {
        npc.nextTurn = 0;
        npc.vx *= -1;
        npc.vy *= -1;
      } else {
        npc.x = nextX;
        npc.y = nextY;
      }

      const movingSideways = Math.abs(npc.vx) > Math.abs(npc.vy);
      const texture = movingSideways ? "npc-side" : npc.vy < 0 ? "npc-back" : "npc-front";
      npc.sprite.setTexture(texture);
      npc.sprite.setFlipX(movingSideways && npc.vx < 0);
      const bob = Math.sin(time / 170 + npc.phase) * (movingSideways ? 1.5 : 0.7);
      npc.sprite.setPosition(npc.x, npc.y - 14 + bob);
      npc.shadow.setPosition(npc.x, npc.y + 18);
      npc.shadow.setScale(movingSideways ? 1.05 : 0.95, 1);
      npc.nameLabel.setPosition(npc.x, npc.y - 47 + bob);
      npc.shadow.setDepth(npc.y - 1);
      npc.sprite.setDepth(npc.y + 10);
      npc.nameLabel.setDepth(npc.y + 11);
    });
  }

  npcBlocked(npc, x, y) {
    const [minX, minY, maxX, maxY] = npc.bounds;
    if (x < minX || x > maxX || y < minY || y > maxY) return true;
    const hitsBuilding = this.buildings.getChildren().some((building) => {
      const bounds = building.getBounds();
      return x > bounds.left - 14 && x < bounds.right + 14 &&
        y > bounds.top - 10 && y < bounds.bottom + 8;
    });
    if (hitsBuilding) return true;
    return Phaser.Math.Distance.Between(x, y, this.player.x, this.player.y) < 28;
  }

  update() {
    this.updateNPCs(this.time.now, this.game.loop.delta);
    const body = this.player.body;
    body.setVelocity(0);
    const speed = 160;
    if (this.cursors.left.isDown || this.wasd.A.isDown) body.setVelocityX(-speed);
    if (this.cursors.right.isDown || this.wasd.D.isDown) body.setVelocityX(speed);
    if (this.cursors.up.isDown || this.wasd.W.isDown) body.setVelocityY(-speed);
    if (this.cursors.down.isDown || this.wasd.S.isDown) body.setVelocityY(speed);
    body.velocity.normalize().scale(speed);
    this.player.setDepth(this.player.y + 12);

    if (document.getElementById("panel").classList.contains("open")) {
      body.setVelocity(0);
      return;
    }

    this.near = null;
    this.doors.forEach((door) => {
      const d = Phaser.Math.Distance.Between(this.player.x, this.player.y, door.x, door.y);
      if (d < 36) this.near = door.storeId;
    });
    this.hint.setText(this.near ? `Press E to enter ${this.near.toUpperCase()}` : "Walk to a doorway and press E");

    if (Phaser.Input.Keyboard.JustDown(this.wasd.E) && this.near && !this.busy) {
      this.enterStore(this.near);
    }
  }

  enterStore(id) {
    if (id === "arcade") {
      this.scene.start("ArcadeScene");
      return;
    }
    const copy = {
      photo: ["Photography Studio", "What should I photograph?"],
      post: ["Post Office", "What message should we send out of town?"],
      bank: ["Bank", "Ask the teller for today's rates."],
      library: ["Library", "What do you want to look up?"],
    }[id];
    this.openPanel(copy[0], copy[1], id);
  }

  openPanel(title, body, id) {
    document.getElementById("panel-title").textContent = title;
    document.getElementById("panel-body").textContent = body;
    document.getElementById("status").textContent = "";
    const form = document.getElementById("panel-form");
    form.innerHTML = "";
    if (id === "bank") {
      const go = document.createElement("button");
      go.textContent = "Get live prices";
      go.onclick = async () => {
        this.setStatus("Looking up a live rate...");
        try {
          const data = await api.bank();
          this.showCryptoPrices(data);
          this.setStatus(`Live prices from ${data.via || "market data"}.`);
        } catch (err) {
          this.setStatus(err.message);
        }
      };
      form.appendChild(go);
    } else if (id === "library") {
      const chat = document.createElement("div");
      chat.id = "library-chat";
      form.appendChild(chat);
      const input = document.createElement("textarea");
      input.id = "library-input";
      input.rows = 2;
      input.placeholder = "Ask the librarian anything...";
      const go = document.createElement("button");
      go.textContent = "Ask";
      go.onclick = () => this.submitStore(id, input.value);
      form.appendChild(input);
      form.appendChild(go);
      this.renderLibraryMessages([]);
    } else {
      const input = document.createElement(id === "post" ? "textarea" : "input");
      input.rows = 3;
      input.placeholder = id === "photo" ? "a red bicycle under streetlights" : "Type here";
      const go = document.createElement("button");
      go.textContent = id === "photo" ? "Take the picture" : id === "post" ? "Send" : "Ask";
      go.onclick = () => this.submitStore(id, input.value);
      form.appendChild(input);
      form.appendChild(go);
    }
    document.getElementById("panel").classList.add("open");
  }

  async submitStore(id, value) {
    this.setStatus("Calling the store...");
    try {
      if (id === "photo") {
        const data = await api.photograph(value);
        this.setStatus("Print is ready.");
        const img = document.createElement("img");
        img.src = data.image_url;
        document.getElementById("panel-form").appendChild(img);
      } else if (id === "post") {
        await api.postOffice(value);
        this.setStatus("Sent through Nango.");
      } else if (id === "library") {
        const data = await api.library(value);
        this.renderLibraryMessages(data.messages || []);
        const input = document.getElementById("library-input");
        if (input) input.value = "";
        this.setStatus("");
      }
    } catch (err) {
      this.setStatus(err.message);
    }
  }

  setStatus(text) {
    document.getElementById("status").textContent = text;
  }

  renderCryptoPrices(data) {
    const form = document.getElementById("panel-form");
    const old = form.querySelector(".coin-grid");
    if (old) old.remove();
    const grid = document.createElement("div");
    grid.className = "coin-grid";
    [
      ["Bitcoin", data.bitcoin],
      ["Ethereum", data.ethereum],
    ].forEach(([name, coin]) => {
      const card = document.createElement("div");
      card.className = "coin-card";
      const change = Number(coin?.change_24h);
      const direction = change >= 0 ? "up" : "down";
      const title = document.createElement("strong");
      title.textContent = name;
      const price = document.createElement("div");
      price.textContent = `$${Number(coin?.usd || 0).toLocaleString()}`;
      const movement = document.createElement("span");
      movement.className = direction;
      movement.textContent = `${change >= 0 ? "+" : ""}${change.toFixed(2)}% today`;
      card.append(title, price, movement);
      grid.appendChild(card);
    });
    form.prepend(grid);
  }

  showCryptoPrices(data) {
    this.renderCryptoPrices(data);
  }

  renderLibraryMessages(messages) {
    const chat = document.getElementById("library-chat");
    if (!chat) return;
    chat.innerHTML = "";
    messages.forEach((message) => {
      const line = document.createElement("p");
      line.className = "chat-line";
      const speaker = message.role === "user" ? "You" : "Librarian";
      const label = document.createElement("strong");
      label.textContent = `${speaker}:`;
      line.append(label, document.createTextNode(` ${message.content}`));
      chat.appendChild(line);
    });
    chat.scrollTop = chat.scrollHeight;
  }

  closePanel() {
    document.getElementById("panel").classList.remove("open");
  }
}
