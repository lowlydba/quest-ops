"use strict";
const { spawnSync } = require("child_process");

function python() {
  for (const p of ["python3", "python"]) {
    if (spawnSync(p, ["--version"], { stdio: "ignore" }).status === 0) return p;
  }
  throw new Error("python3 not found on this runner");
}

module.exports = { python };
