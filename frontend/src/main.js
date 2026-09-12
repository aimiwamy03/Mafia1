import { TownScene } from "./scenes/TownScene.js";
import { ArcadeScene } from "./scenes/ArcadeScene.js";

const config = {
  type: Phaser.AUTO,
  parent: document.body,
  width: 960,
  height: 640,
  backgroundColor: "#3d6b32",
  pixelArt: true,
  physics: {
    default: "arcade",
    arcade: { gravity: { y: 0 }, debug: false },
  },
  scene: [TownScene, ArcadeScene],
  scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
};

window.addEventListener("load", () => {
  // eslint-disable-next-line no-new
  new Phaser.Game(config);
});
