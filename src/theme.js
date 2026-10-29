/* theme.js
 *
 * The portfolio's theme toggle (nathancouturier.github.io, script.js), kept as
 * close to the original as the declared differences allow, as the sibling
 * studies (crack-spread-study, jkm-ttf-arbitrage) keep it.
 *
 * Kept from the portfolio: data-theme on <html>; the localStorage key nc-theme,
 * shared with the portfolio because both sites are on the same origin; light
 * unless the store says otherwise, with the system prefers-color-scheme ignored
 * as the portfolio ignores it; the glyph swapped to a sun in dark and a moon in
 * light; meta theme-color rewritten to #17181C or #FBFAF8; aria-label "Toggle
 * theme" and title "Press T to toggle"; the key T toggling unless the target is
 * a field or a modifier is held.
 *
 * Declared differences:
 *   1  the key listener also ignores select and [contenteditable]
 *   2  every localStorage access sits inside try, so a blocked store falls back
 *      to light instead of throwing
 *   3  an inline script in index.html's head sets data-theme before the first
 *      paint; this module takes over after load
 *   4  the button also sets aria-pressed to whether dark is on
 *   5  each glyph is followed by U+FE0E, the text presentation selector, so no
 *      platform draws it as a colour emoji
 *
 * The glyphs are built from their code points, so this file holds no character
 * outside ASCII. Numeric literals: the four code points, declared in
 * tools/check-literals.mjs.
 */

const STORAGE_KEY = "nc-theme";
const SUN = 0x2600;
const MOON = 0x263e;
const TEXT_PRESENTATION = 0xfe0e;
const GLYPH_DARK = String.fromCharCode(SUN, TEXT_PRESENTATION);
const GLYPH_LIGHT = String.fromCharCode(MOON, TEXT_PRESENTATION);
const THEME_COLOR_DARK = "#17181C";
const THEME_COLOR_LIGHT = "#FBFAF8";

const root = document.documentElement;
const state = { theme: readStored() };

function readStored() {
  try {
    return localStorage.getItem(STORAGE_KEY) === "dark" ? "dark" : "light";
  } catch (error) {
    return "light";
  }
}

export function applyTheme(theme) {
  state.theme = theme;
  root.setAttribute("data-theme", theme);
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch (error) {
    /* storage blocked: the choice lasts for this page only */
  }
  const icon = document.querySelector("#theme-icon");
  if (icon) icon.textContent = theme === "dark" ? GLYPH_DARK : GLYPH_LIGHT;
  const button = document.querySelector("#theme-toggle");
  if (button) button.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.content = theme === "dark" ? THEME_COLOR_DARK : THEME_COLOR_LIGHT;
}

export function toggleTheme() {
  applyTheme(state.theme === "dark" ? "light" : "dark");
}

export function currentTheme() {
  return state.theme;
}

/** Wire the button and the T key, and apply the stored theme once. */
export function initTheme() {
  const button = document.querySelector("#theme-toggle");
  if (button) button.addEventListener("click", toggleTheme);
  document.addEventListener("keydown", (ev) => {
    const target = ev.target;
    if (target && target.matches && target.matches("input, textarea, select, [contenteditable], [contenteditable] *")) return;
    if (ev.metaKey || ev.ctrlKey || ev.altKey) return;
    if (ev.key === "t" || ev.key === "T") {
      ev.preventDefault();
      toggleTheme();
    }
  });
  applyTheme(state.theme);
}
