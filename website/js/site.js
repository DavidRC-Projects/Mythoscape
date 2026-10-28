(() => {
  // Change before you share the link. Friends type this once; it sticks in localStorage.
  const INVITE_CODE = "CROWNFALL-FRIENDS";

  const gate = document.getElementById("gate");
  const panel = document.getElementById("download-panel");
  const input = document.getElementById("invite");
  const unlock = document.getElementById("unlock");
  const err = document.getElementById("gate-err");
  const KEY = "crownfall_beta_ok";

  function openDownloads() {
    gate.classList.remove("is-open");
    panel.classList.add("is-open");
  }

  function tryUnlock(raw) {
    const code = String(raw || "").trim();
    if (code.toUpperCase() === INVITE_CODE.toUpperCase()) {
      localStorage.setItem(KEY, "1");
      err.textContent = "";
      openDownloads();
      return;
    }
    err.textContent = "That code is not on the guest list.";
  }

  if (localStorage.getItem(KEY) === "1") {
    openDownloads();
  } else {
    gate.classList.add("is-open");
  }

  unlock.addEventListener("click", () => tryUnlock(input.value));
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") tryUnlock(input.value);
  });
})();
