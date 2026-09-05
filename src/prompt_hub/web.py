from prompt_hub.comfy_web import COMFY_HTML, COMFY_SCRIPT, COMFY_STYLES
from prompt_hub.creative_web import CREATIVE_HTML, CREATIVE_SCRIPT, CREATIVE_STYLES
from prompt_hub.lora_web import LORA_HTML, LORA_SCRIPT, LORA_STYLES
from prompt_hub.remote_web import REMOTE_HTML, REMOTE_SCRIPT, REMOTE_STYLES
from prompt_hub.search_web import SEARCH_HTML, SEARCH_SCRIPT, SEARCH_STYLES
from prompt_hub.source_center_web import (
    SOURCE_CENTER_HTML,
    SOURCE_CENTER_SCRIPT,
    SOURCE_CENTER_STYLES,
)
from prompt_hub.workspace_web import WORKSPACE_HTML, WORKSPACE_SCRIPT, WORKSPACE_STYLES

INDEX_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Soda Prompt Hub</title>
  <meta name="application-name" content="Soda Prompt Hub">
  <meta name="description" content="Soda 的本地 AI 绘图提示词、视觉参考与 OC 创作中枢。">
  <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' fill='%23171815'/%3E%3Cpath d='M12 16h40v10H12zm0 22h26v10H12z' fill='%23d84b2a'/%3E%3Ccircle cx='48' cy='43' r='7' fill='%23d7e455'/%3E%3C/svg%3E">
  <style>
    :root {
      --ink: #171815;
      --paper: #ece8dc;
      --paper-deep: #d8d1bf;
      --signal: #a33822;
      --acid: #d7e455;
      --muted: #5b5a53;
      --line: rgba(23, 24, 21, .19);
      --shadow: 0 22px 55px rgba(29, 27, 20, .14);
    }
    * { box-sizing: border-box; }
    html { background: #20211e; scroll-behavior: smooth; }
    body {
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      background:
        radial-gradient(circle at 18% 12%, rgba(215, 228, 85, .11), transparent 30%),
        linear-gradient(115deg, #292a25 0 33%, #1c1d1a 33% 100%);
      font-family: "Avenir Next", "Helvetica Neue", sans-serif;
    }
    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      opacity: .17;
      background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 180 180' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='.25'/%3E%3C/svg%3E");
      mix-blend-mode: soft-light;
    }
    .shell { width: min(1480px, calc(100% - 32px)); margin: 0 auto; padding: 28px 0 60px; }
    button, input, select, textarea { font: inherit; }
    button { border: 0; background: transparent; color: inherit; }
    button:focus-visible, input:focus-visible, select:focus-visible, textarea:focus-visible, a:focus-visible {
      outline: 3px solid var(--acid);
      outline-offset: 3px;
    }
    .app-nav {
      min-height: 62px;
      margin-bottom: 18px;
      display: flex;
      align-items: stretch;
      justify-content: space-between;
      background: var(--paper);
      box-shadow: var(--shadow);
      border: 1px solid rgba(255,255,255,.18);
    }
    .app-brand {
      border: 0;
      border-right: 1px solid var(--line);
      background: var(--ink);
      color: var(--paper);
      padding: 0 24px;
      cursor: pointer;
      text-align: left;
      font: 800 13px/1 "Iowan Old Style", serif;
      letter-spacing: .04em;
    }
    .app-brand span { display: block; margin-top: 5px; color: var(--acid); font: 700 8px/1 monospace; letter-spacing: .18em; text-transform: uppercase; }
    .app-nav-items { display: flex; align-items: stretch; overflow-x: auto; }
    .app-nav-button {
      min-width: 122px;
      border: 0;
      border-left: 1px solid var(--line);
      background: transparent;
      color: var(--muted);
      padding: 0 18px;
      cursor: pointer;
      font: 800 11px/1 monospace;
      letter-spacing: .08em;
      transition: color .18s ease, background .18s ease;
    }
    .app-nav-button:hover { color: var(--ink); background: #e2dccd; }
    .app-nav-button[aria-current="page"] { background: var(--signal); color: #fff8eb; }
    .tag-language-button { color: var(--ink); background: var(--acid); }
    .home-page {
      display: grid;
      grid-template-columns: minmax(0, 1.35fr) minmax(310px, .65fr);
      gap: 18px;
      align-items: stretch;
    }
    .home-lead, .home-guide, .home-footnote { background: var(--paper); box-shadow: var(--shadow); }
    .home-lead { min-height: 590px; padding: clamp(34px, 6vw, 78px); position: relative; overflow: hidden; }
    .home-lead::after {
      content: "开始 / 01";
      position: absolute;
      right: -24px;
      bottom: 74px;
      color: rgba(23,24,21,.08);
      font: 800 clamp(48px, 8vw, 110px)/1 monospace;
      letter-spacing: -.08em;
      transform: rotate(-90deg);
    }
    .home-lead h1 { margin-top: 28px; max-width: 820px; font-size: clamp(58px, 8vw, 116px); }
    .home-lead .subtitle { max-width: 690px; font-size: 16px; }
    .home-actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 38px; position: relative; z-index: 1; }
    .home-primary, .home-secondary {
      border: 1px solid var(--ink);
      padding: 15px 18px;
      cursor: pointer;
      font: 800 11px/1 monospace;
      letter-spacing: .1em;
      transition: transform .18s ease, box-shadow .18s ease, background .18s ease;
    }
    .home-primary { background: var(--signal); border-color: var(--signal); color: #fff8eb; }
    .home-secondary { background: transparent; color: var(--ink); }
    .home-primary:hover, .home-secondary:hover { transform: translate(-2px, -2px); box-shadow: 5px 5px 0 var(--ink); }
    .home-example {
      display: block;
      margin-top: 16px;
      border: 0;
      border-bottom: 1px solid var(--line);
      background: transparent;
      color: var(--signal);
      padding: 8px 0;
      cursor: pointer;
      text-align: left;
      font: 800 10px/1.4 monospace;
      letter-spacing: .06em;
      position: relative;
      z-index: 1;
    }
    .home-example:hover { border-bottom-color: var(--signal); }
    .home-targets { margin-top: 60px; max-width: 700px; border-top: 1px solid var(--line); padding-top: 20px; position: relative; z-index: 1; }
    .target-row { display: grid; grid-template-columns: 92px 1fr; gap: 14px; padding: 10px 0; border-bottom: 1px solid var(--line); }
    .target-row strong { color: var(--signal); font: 800 10px/1.35 monospace; letter-spacing: .09em; }
    .target-row span { color: #55564f; font-size: 13px; line-height: 1.5; }
    .home-guide { padding: 34px; background: var(--ink); color: var(--paper); display: flex; flex-direction: column; }
    .home-guide h2 { margin: 18px 0 30px; font: 700 36px/1 "Iowan Old Style", serif; letter-spacing: -.035em; }
    .guide-steps { display: grid; gap: 0; }
    .guide-step { display: grid; grid-template-columns: 42px 1fr; gap: 14px; padding: 18px 0; border-top: 1px solid rgba(236,232,220,.2); }
    .guide-step:last-child { border-bottom: 1px solid rgba(236,232,220,.2); }
    .guide-step > span { color: var(--acid); font: 800 20px/1 "Iowan Old Style", serif; }
    .guide-step strong { display: block; font-size: 13px; }
    .guide-step small { display: block; margin-top: 7px; color: #aaa99f; font-size: 11px; line-height: 1.55; }
    .home-status { margin-top: auto; padding-top: 28px; }
    .home-status-line { display: flex; justify-content: space-between; gap: 18px; padding: 9px 0; color: #aaa99f; font: 700 10px/1 monospace; letter-spacing: .08em; }
    .home-status-line strong { color: var(--acid); font-size: 15px; }
    .home-footnote { grid-column: 1 / -1; padding: 18px 24px; display: flex; justify-content: space-between; gap: 24px; align-items: center; }
    .home-footnote p { margin: 0; color: #55564f; font-size: 12px; line-height: 1.6; }
    .home-footnote strong { color: var(--ink); }
    .management-page { display: grid; gap: 18px; }
    .management-sources { padding: 28px; background: var(--paper); box-shadow: var(--shadow); }
    .management-sources .source-list { grid-template-columns: repeat(2, minmax(0, 1fr)); margin-top: 0; padding-top: 0; border-top: 0; }
    .management-sources .source-row { padding: 13px 0; border-bottom: 1px solid var(--line); }
    .sync-actions { display: grid; gap: 9px; width: min(100%, 300px); }
    .source-sync-message { min-height: 38px; margin: 18px 0 0; border-left: 4px solid var(--acid); background: #e6dfd0; padding: 10px 12px; font: 800 9px/1.5 monospace; }
    .source-sync-list { display: grid; gap: 0; margin-top: 18px; border-top: 1px solid var(--line); }
    .source-sync-row { display: grid; grid-template-columns: minmax(150px, 1fr) auto minmax(180px, .8fr); gap: 12px; align-items: center; padding: 11px 0; border-bottom: 1px solid var(--line); font-size: 11px; }
    .source-sync-row strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .source-sync-row code { color: var(--muted); font-size: 9px; }
    .source-sync-state { padding: 5px 7px; background: var(--paper-deep); color: var(--ink); font: 900 8px monospace; }
    .source-sync-state.ready { background: var(--acid); }
    .source-sync-state.dirty, .source-sync-state.failed { background: var(--signal); color: white; }
    .archive-notice { margin: 0 0 18px; padding: 14px 16px; background: #ded7c7; border-left: 4px solid var(--signal); color: #55564f; font-size: 12px; line-height: 1.6; }
    .archive-notice strong { color: var(--ink); }
    .archive-header {
      display: grid;
      grid-template-columns: minmax(0, 1.35fr) minmax(290px, .65fr);
      min-height: 230px;
      background: var(--paper);
      border: 1px solid rgba(255,255,255,.18);
      box-shadow: var(--shadow);
      overflow: hidden;
    }
    .masthead { padding: 34px 38px 30px; position: relative; }
    .eyebrow {
      display: inline-flex;
      gap: 9px;
      align-items: center;
      font: 700 11px/1 "SFMono-Regular", Consolas, monospace;
      letter-spacing: .18em;
      text-transform: uppercase;
    }
    .eyebrow::before { content: ""; width: 25px; height: 8px; background: var(--signal); }
    h1 {
      margin: 18px 0 12px;
      max-width: 760px;
      font-family: "Iowan Old Style", "Palatino Linotype", Palatino, serif;
      font-size: clamp(42px, 7vw, 92px);
      line-height: .87;
      letter-spacing: -.055em;
      font-weight: 700;
    }
    .subtitle { margin: 0; max-width: 620px; color: #55564f; font-size: 14px; line-height: 1.7; }
    .stamp {
      position: absolute;
      right: 28px;
      bottom: 26px;
      border: 2px solid var(--signal);
      color: var(--signal);
      padding: 8px 12px 6px;
      font: 800 10px/1 "SFMono-Regular", monospace;
      letter-spacing: .15em;
      text-transform: uppercase;
      transform: rotate(-5deg);
    }
    .stats-panel {
      position: relative;
      background: var(--ink);
      color: var(--paper);
      padding: 30px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }
    .stats-panel::after {
      content: "本机资料";
      position: absolute;
      right: -35px;
      top: 48%;
      transform: rotate(90deg);
      color: rgba(236,232,220,.15);
      font: 700 10px/1 monospace;
      letter-spacing: .4em;
    }
    .stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
    .stat { border-top: 1px solid rgba(236,232,220,.26); padding-top: 10px; }
    .stat strong { display: block; font: 700 32px/1 "Iowan Old Style", serif; color: var(--acid); }
    .stat span { display: block; margin-top: 6px; color: #a8a79e; font: 600 10px/1.2 monospace; text-transform: uppercase; letter-spacing: .12em; }
    .personal-summary {
      margin: 17px 0;
      padding: 10px 12px;
      border: 1px solid rgba(215,228,85,.38);
      color: #b9b9ad;
      font: 700 10px/1.2 monospace;
      letter-spacing: .1em;
      text-transform: uppercase;
    }
    .personal-summary strong { color: var(--acid); font-size: 14px; }
    .personal-summary .divider { padding: 0 7px; color: rgba(236,232,220,.72); }
    .stats-panel .section-label { color: #b9ae9f; }
    .sync-button {
      border: 1px solid var(--acid);
      color: var(--acid);
      background: transparent;
      padding: 12px 15px;
      text-align: left;
      font: 700 11px/1 monospace;
      letter-spacing: .1em;
      cursor: pointer;
      transition: .18s ease;
    }
    .sync-button:hover { background: var(--acid); color: var(--ink); transform: translateY(-2px); }
    .workspace {
      margin-top: 18px;
      display: grid;
      grid-template-columns: 310px minmax(0, 1fr);
      gap: 18px;
      align-items: start;
    }
    #archiveWorkspace .section-label, #archiveWorkspace label, #managementPage .section-label, #managementPage .stat span, #managementPage .personal-summary { text-transform: none; }
    aside, main { background: var(--paper); box-shadow: var(--shadow); }
    aside { padding: 24px; position: sticky; top: 18px; }
    .section-label {
      margin: 0 0 14px;
      font: 800 10px/1 monospace;
      letter-spacing: .16em;
      text-transform: uppercase;
      color: var(--muted);
    }
    [hidden] { display: none !important; }
    .mode-switch {
      display: grid;
      grid-template-columns: 1fr 1fr;
      margin: 0 0 22px;
      border: 1px solid var(--ink);
    }
    .mode-button {
      border: 0;
      background: transparent;
      color: var(--muted);
      padding: 11px 8px 10px;
      cursor: pointer;
      font: 800 9px/1 monospace;
      letter-spacing: .1em;
    }
    .mode-button + .mode-button { border-left: 1px solid var(--ink); }
    .mode-button[aria-pressed="true"] { background: var(--ink); color: var(--acid); }
    .search-box { position: relative; }
    input, select {
      width: 100%;
      border: 0;
      border-bottom: 1px solid var(--ink);
      border-radius: 0;
      background: transparent;
      color: var(--ink);
      padding: 12px 2px;
      font: 600 14px/1.2 "Avenir Next", sans-serif;
      outline: none;
    }
    input:focus, select:focus { border-bottom-color: var(--signal); box-shadow: 0 2px 0 var(--signal); }
    .filters { display: grid; gap: 16px; margin-top: 24px; }
    .advanced-filters { margin-top: 18px; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }
    .advanced-filters summary {
      padding: 12px 0;
      cursor: pointer;
      color: var(--muted);
      font: 800 10px/1 monospace;
      letter-spacing: .1em;
      list-style: none;
    }
    .advanced-filters summary::-webkit-details-marker { display: none; }
    .advanced-filters summary::after { content: "+"; float: right; color: var(--signal); font-size: 15px; }
    .advanced-filters[open] summary::after { content: "−"; }
    .advanced-filters .filters { margin: 0; padding: 5px 0 18px; }
    label { display: grid; gap: 4px; font: 700 10px/1 monospace; letter-spacing: .1em; text-transform: uppercase; color: var(--muted); }
    .search-button {
      width: 100%;
      margin-top: 24px;
      border: 0;
      background: var(--signal);
      color: #fff8eb;
      padding: 14px;
      font: 800 11px/1 monospace;
      letter-spacing: .15em;
      cursor: pointer;
      transition: .18s ease;
    }
    .search-button:hover { transform: translate(-2px, -2px); box-shadow: 5px 5px 0 var(--ink); }
    .shelf-filter {
      width: 100%;
      margin-top: 12px;
      border: 1px solid var(--ink);
      background: transparent;
      color: var(--ink);
      padding: 11px 12px;
      text-align: left;
      font: 800 10px/1 monospace;
      letter-spacing: .12em;
      cursor: pointer;
    }
    .shelf-filter[aria-pressed="true"] { background: var(--ink); color: var(--acid); }
    .source-list { margin: 28px 0 0; padding: 18px 0 0; border-top: 1px solid var(--line); display: grid; gap: 12px; }
    .source-row { display: flex; justify-content: space-between; gap: 12px; font-size: 12px; }
    .source-row span:last-child { font: 700 11px monospace; color: var(--signal); }
    .oc-import-panel {
      margin-top: 24px;
      padding: 16px;
      border: 1px dashed var(--line);
      background: #e2dccd;
    }
    .oc-import-panel p { margin: 0; }
    .file-picker, .oc-import-button {
      display: block;
      width: 100%;
      border: 1px solid var(--ink);
      background: transparent;
      color: var(--ink);
      padding: 11px 12px;
      text-align: left;
      cursor: pointer;
      font: 800 9px/1 monospace;
      letter-spacing: .1em;
    }
    .file-picker:hover, .oc-import-button:hover:not(:disabled) { background: var(--ink); color: var(--acid); }
    .oc-import-button { margin-top: 8px; background: var(--signal); border-color: var(--signal); color: #fff8eb; }
    .oc-import-button:disabled { opacity: .42; cursor: not-allowed; }
    .file-name { margin-top: 9px !important; color: var(--muted); font: 600 10px/1.4 monospace; overflow-wrap: anywhere; }
    .import-message { margin-top: 9px !important; color: var(--signal); font: 700 10px/1.45 monospace; }
    main { min-height: 630px; padding: 24px 28px 34px; }
    .results-head { display: flex; justify-content: space-between; align-items: baseline; border-bottom: 1px solid var(--line); padding-bottom: 14px; }
    .results-head h2 { margin: 0; font: 700 28px/1 "Iowan Old Style", serif; letter-spacing: -.03em; }
    #status { color: var(--muted); font: 600 11px monospace; }
    .results { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1px; background: var(--line); margin-top: 18px; border: 1px solid var(--line); }
    .results.character-results { gap: 12px; background: transparent; border: 0; }
    .results.character-results .character-card { border: 1px solid var(--line); }
    .card {
      min-width: 0;
      background: var(--paper);
      padding: 20px;
      position: relative;
      transition: background .18s ease;
      animation: reveal .35s both;
    }
    .card:hover { background: #f5f0e4; z-index: 2; }
    .card.is-favorite { box-shadow: inset 4px 0 0 var(--signal); }
    .character-card { min-height: 310px; display: flex; flex-direction: column; }
    .character-mark {
      height: 112px;
      margin: -20px -20px 18px;
      padding: 19px;
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      overflow: hidden;
      position: relative;
      color: var(--paper);
      background:
        linear-gradient(135deg, transparent 0 48%, rgba(215,228,85,.2) 48% 52%, transparent 52%),
        linear-gradient(115deg, #171815 0 60%, #d84b2a 60% 100%);
    }
    .character-mark::before {
      content: attr(data-initial);
      position: absolute;
      right: 18px;
      top: -22px;
      color: rgba(236,232,220,.13);
      font: 700 116px/1 "Iowan Old Style", serif;
    }
    .character-mark span { position: relative; font: 800 9px/1 monospace; letter-spacing: .14em; text-transform: uppercase; }
    .character-meta { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 7px 14px; margin: 13px 0 0; }
    .character-meta span { color: var(--muted); font: 600 10px/1.35 monospace; overflow-wrap: anywhere; }
    .character-meta strong { color: var(--ink); }
    .character-actions { margin-top: auto; padding-top: 17px; }
    .detail-button {
      width: 100%;
      border: 1px solid var(--ink);
      background: transparent;
      color: var(--ink);
      padding: 10px 12px;
      text-align: left;
      cursor: pointer;
      font: 800 9px/1 monospace;
      letter-spacing: .12em;
    }
    .detail-button:hover, .detail-button[aria-expanded="true"] { background: var(--ink); color: var(--acid); }
    .character-detail { margin-top: 12px; padding: 14px; background: #ded7c7; border-left: 3px solid var(--signal); }
    .character-detail h4 { margin: 16px 0 7px; font: 700 15px/1.1 "Iowan Old Style", serif; }
    .character-detail h4:first-child { margin-top: 0; }
    .character-detail p { margin: 0; color: #4f5049; font-size: 11px; line-height: 1.6; white-space: pre-wrap; }
    .detail-counts { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 12px; }
    .detail-counts span { padding: 5px 7px; background: var(--paper); color: var(--muted); font: 700 9px/1 monospace; }
    .prompt-record { margin-top: 7px; padding: 8px; background: var(--paper); }
    .prompt-record strong { display: block; color: var(--signal); font: 800 9px/1.3 monospace; }
    .prompt-record p { margin-top: 4px; }
    .visual-gallery {
      display: grid;
      grid-template-columns: repeat(var(--visual-count), minmax(0, 1fr));
      position: relative;
      aspect-ratio: 4 / 3;
      margin: -20px -20px 18px;
      overflow: hidden;
      background: #c9c2b1;
      border-bottom: 1px solid var(--line);
      gap: 1px;
    }
    .visual-frame {
      display: block;
      position: relative;
      min-width: 0;
      overflow: hidden;
      background: #c9c2b1;
    }
    .visual-frame img {
      width: 100%;
      height: 100%;
      display: block;
      object-fit: cover;
      filter: saturate(.9) contrast(1.03);
      transition: transform .45s cubic-bezier(.2,.75,.2,1), filter .3s ease;
    }
    .visual-frame:hover img { transform: scale(1.035); filter: saturate(1.05) contrast(1.02); }
    .visual-label, .visual-safety {
      position: absolute;
      bottom: 10px;
      background: rgba(23,24,21,.88);
      color: var(--paper);
      padding: 7px 9px 6px;
      font: 800 9px/1 monospace;
      letter-spacing: .1em;
      backdrop-filter: blur(8px);
    }
    .visual-label { left: 10px; }
    .visual-safety { right: 10px; top: 10px; bottom: auto; }
    .visual-gallery.multi .visual-label { left: 6px; bottom: 6px; padding: 6px; }
    .visual-gallery.multi .visual-safety { right: 6px; top: 6px; padding: 5px; font-size: 8px; }
    .visual-safety.suggestive { background: rgba(216,75,42,.92); }
    .visual-safety.explicit-adult { background: rgba(125,22,22,.94); color: #fff4e9; }
    .card-meta { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 13px; }
    .badge { padding: 5px 7px 4px; background: var(--ink); color: var(--paper); font: 700 9px/1 monospace; letter-spacing: .08em; text-transform: uppercase; }
    .badge.signal { background: var(--signal); }
    .badge.soft { background: var(--paper-deep); color: var(--ink); }
    .card h3 { margin: 0 0 9px; font: 700 19px/1.15 "Iowan Old Style", serif; }
    .content {
      margin: 0;
      color: #484941;
      font-size: 13px;
      line-height: 1.65;
      display: -webkit-box;
      -webkit-line-clamp: 6;
      -webkit-box-orient: vertical;
      overflow: hidden;
      white-space: pre-wrap;
    }
    .personal-tools {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
      margin: 17px 0 0;
      padding-top: 13px;
      border-top: 1px dashed var(--line);
    }
    .favorite-button, .note-button, .star-button, .save-note-button {
      border: 0;
      background: transparent;
      color: var(--muted);
      cursor: pointer;
      font: 800 9px/1 monospace;
      letter-spacing: .08em;
    }
    .favorite-button { padding: 7px 9px; border: 1px solid var(--line); }
    .favorite-button[aria-pressed="true"] { background: var(--signal); border-color: var(--signal); color: #fff8eb; }
    .rating-control { display: flex; gap: 1px; margin-left: auto; }
    .star-button { padding: 5px 2px; font-size: 15px; color: #67655d; }
    .star-button.active { color: var(--signal); }
    .note-button { padding: 7px 5px; }
    .note-button.has-note { color: var(--signal); }
    .note-preview {
      margin: 10px 0 0;
      padding: 9px 10px;
      background: #dfd8c8;
      color: #55564f;
      font-size: 11px;
      line-height: 1.5;
      white-space: pre-wrap;
    }
    .note-preview::before { content: "PERSONAL NOTE / "; color: var(--signal); font: 800 9px monospace; letter-spacing: .08em; }
    .note-editor { display: grid; grid-template-columns: 1fr auto; gap: 8px; margin-top: 9px; }
    .note-editor[hidden] { display: none; }
    .note-editor textarea {
      min-height: 68px;
      resize: vertical;
      border: 1px solid var(--line);
      background: #f5f0e4;
      color: var(--ink);
      padding: 9px;
      font: 12px/1.5 "Avenir Next", sans-serif;
    }
    .save-note-button { align-self: stretch; background: var(--ink); color: var(--acid); padding: 0 11px; }
    .card footer { margin-top: 16px; display: flex; justify-content: space-between; align-items: center; gap: 10px; }
    .card footer span { color: var(--muted); font: 600 10px monospace; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .card a { color: var(--signal); font: 800 10px monospace; text-decoration: none; text-transform: uppercase; }
    .empty { grid-column: 1 / -1; padding: 90px 30px; text-align: center; background: var(--paper); }
    .empty strong { display: block; font: 700 32px "Iowan Old Style", serif; }
    .empty span { color: var(--muted); font-size: 13px; }
    @keyframes reveal { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
    @media (max-width: 900px) {
      .app-nav { display: block; }
      .app-brand { width: 100%; min-height: 58px; border-right: 0; }
      .app-nav-items { width: 100%; display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); overflow: visible; }
      .app-nav-button { min-width: 0; min-height: 46px; padding: 0 8px; border-bottom: 1px solid var(--line); }
      .archive-header, .workspace, .home-page { grid-template-columns: 1fr; }
      aside { position: static; }
      .stats-panel { min-height: 220px; }
      .home-lead { min-height: auto; }
      .home-guide { min-height: 500px; }
    }
    @media (max-width: 620px) {
      .shell { width: min(100% - 18px, 1480px); padding-top: 9px; }
      .app-nav-items { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .app-nav-button { min-height: 48px; padding: 0 12px; }
      .home-lead, .home-guide { padding: 28px 22px; }
      .home-lead h1 { font-size: 58px; }
      .home-actions { display: grid; }
      .home-primary, .home-secondary { width: 100%; text-align: left; }
      .home-footnote { display: block; }
      .home-footnote p + p { margin-top: 8px; }
      .management-sources .source-list { grid-template-columns: 1fr; }
      .source-sync-row { grid-template-columns: 1fr auto; }
      .source-sync-row code { grid-column: 1 / -1; }
      .masthead { padding: 26px 22px 80px; }
      .stats-panel, aside, main { padding: 22px; }
      .results { grid-template-columns: 1fr; }
      h1 { font-size: 50px; }
    }
    @media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation: none !important; transition: none !important; } }
  </style>
</head>
<body>
  <div class="shell">
    <nav class="app-nav" aria-label="主导航">
      <button class="app-brand" data-view="home">Soda Prompt Hub<span>本地绘图与数据集</span></button>
      <div class="app-nav-items">
        <button class="app-nav-button" data-view="creative">创作台</button>
        <button class="app-nav-button" data-view="prompts">提示词库</button>
        <button class="app-nav-button" data-view="discover">智能检索</button>
        <button class="app-nav-button" data-view="characters">角色库</button>
        <button class="app-nav-button" data-view="datasets">数据集</button>
        <button class="app-nav-button" data-view="lora">LoRA 项目</button>
        <button class="app-nav-button" data-view="comfy">Windows 出图</button>
        <button class="app-nav-button" data-view="management">资料管理</button>
        <button class="app-nav-button" data-view="remote">设备连接</button>
        <button class="app-nav-button tag-language-button" id="tagLanguageToggle" type="button">标签：中英</button>
      </div>
    </nav>

    <section class="home-page" id="homePage">
      <div class="home-lead">
        <div class="eyebrow">本地绘图工作台</div>
        <h1>今天想画<br>什么？</h1>
        <p class="subtitle">从一个想法、一个 OC，或者一张视觉参考开始。先把创作资料找齐，再整理成适合 Anima 与 Krea 2 的不同 Prompt。</p>
        <div class="home-actions">
          <button class="home-primary" data-start="creative">新建或继续绘图项目 →</button>
          <button class="home-secondary" data-start="prompts">浏览提示词与视觉参考</button>
          <button class="home-secondary" data-start="characters">从 OC 角色开始</button>
          <button class="home-secondary" data-start="lora">准备 LoRA 数据集</button>
          <button class="home-secondary" data-start="comfy">查看 Windows 出图结果</button>
        </div>
        <button class="home-example" id="exampleButton">试一个真实示例：维多利亚军装 × 黄昏图书馆 ↗</button>
        <div class="home-targets">
          <p class="section-label">首批目标模型</p>
          <div class="target-row"><strong>ANIMA</strong><span>输出 Danbooru/Booru 标签、权重和项目对应的负面词。</span></div>
          <div class="target-row"><strong>KREA 2</strong><span>输出连贯自然语言，保留主体关系、构图、材质、灯光与画风。</span></div>
        </div>
      </div>
      <aside class="home-guide">
        <p class="section-label">日常绘图顺序</p>
        <h2>从想法到可用提示词</h2>
        <div class="guide-steps">
          <div class="guide-step"><span>01</span><div><strong>确定角色和想法</strong><small>可以从空白描述开始，也可以读取 OC Manager 的角色资料。</small></div></div>
          <div class="guide-step"><span>02</span><div><strong>选择提示词与视觉参考</strong><small>从本地库挑选服装、动作、构图、场景、灯光和画风。</small></div></div>
          <div class="guide-step"><span>03</span><div><strong>按模型整理并保存</strong><small>同一份创作意图分别生成 Anima 与 Krea 2 版本，保存为个人配方。</small></div></div>
        </div>
        <div class="home-status">
          <div class="home-status-line"><span>本地资料</span><strong id="homeEntryCount">—</strong></div>
          <div class="home-status-line"><span>视觉与提示来源</span><strong id="homeSourceCount">—</strong></div>
          <div class="home-status-line"><span>已导入 OC</span><strong id="homeOcCount">—</strong></div>
        </div>
      </aside>
      <div class="home-footnote">
        <p><strong>个人版 1.0：</strong>创作、资料引用、双格式输出、远程出图、结果回流与数据集交付已经形成完整闭环。</p>
        <p><strong>设备分工：</strong>Mac 负责整理、审核与保存记录；5060 Ti 的 ComfyUI 负责生成与测试。</p>
      </div>
    </section>

    <section class="management-page" id="managementPage" hidden>
      <header class="archive-header">
        <section class="masthead">
          <div class="eyebrow">本地资料管理</div>
          <h1>资料与<br>索引</h1>
          <p class="subtitle">在这里更新公共资料、查看来源与本地索引状态。创作和日常检索不需要操作这些设置。</p>
          <div class="stamp">只保存在本机</div>
        </section>
        <section class="stats-panel">
          <div>
            <p class="section-label">资料库状态</p>
            <div class="stats-grid">
              <div class="stat"><strong id="entryCount">—</strong><span>资料条目</span></div>
              <div class="stat"><strong id="sourceCount">—</strong><span>资料来源</span></div>
              <div class="stat"><strong id="styleCount">—</strong><span>画风资料</span></div>
              <div class="stat"><strong id="tagCount">—</strong><span>标签</span></div>
            </div>
            <div class="personal-summary">我的收藏 <strong id="favoriteCount">0</strong> 条 <span class="divider">·</span> 已导入角色 <strong id="ocCount">0</strong> 个</div>
          </div>
          <div class="sync-actions"><button class="sync-button" id="sourceSyncButton">↻ 更新公共提示词库</button><button class="sync-button" id="importButton">仅重建本地索引</button></div>
        </section>
      </header>
      <section class="management-sources">
        <p class="section-label">已经可以检索的来源</p>
        <div class="source-list" id="sourceList"></div>
        <div class="source-sync-message" id="sourceSyncMessage">正在读取本地资料源状态…</div>
        <div class="source-sync-list" id="sourceSyncList"></div>
      </section>
    </section>

    <div class="workspace" id="archiveWorkspace" hidden>
      <aside>
        <p class="section-label" id="searchLabel">查找提示词和视觉参考</p>
        <div class="search-box"><input id="query" type="search" aria-label="输入提示词关键词" placeholder="例如：哥特连衣裙、兔耳、逆光" autofocus></div>
        <details class="advanced-filters">
          <summary>展开高级筛选</summary>
          <div class="filters" id="promptFilters">
            <label>资料类型<select id="kind"><option value="">全部类型</option><option value="style">画风</option><option value="prompt">完整提示词</option><option value="modifier">修饰词</option><option value="wildcard">通配词</option><option value="caption">图片说明</option><option value="tag">标签</option></select></label>
            <label>内容分级<select id="safety"><option value="">全部分级</option><option value="sfw">普通</option><option value="suggestive">轻度成人向</option><option value="adult">成人向</option><option value="explicit-adult">明确成人向</option></select></label>
            <label>资料来源<select id="source"><option value="">全部来源</option></select></label>
          </div>
          <div class="filters" id="ocFilters" hidden>
            <label>所属世界<select id="ocWorld"><option value="">全部世界</option></select></label>
          </div>
        </details>
        <button class="search-button" id="searchButton">查找提示词</button>
        <button class="shelf-filter" id="favoritesOnly" aria-pressed="false">☆ 只看我的收藏</button>
        <section class="oc-import-panel" id="ocImportPanel" hidden>
          <p class="section-label">从 OC Manager 导入</p>
          <input id="ocFile" type="file" accept="application/json,.json" hidden>
          <label class="file-picker" for="ocFile">＋ 选择角色 JSON 文件</label>
          <p class="file-name" id="ocFileName">尚未选择文件</p>
          <button class="oc-import-button" id="ocImportButton" disabled>导入到本地角色库</button>
          <p class="import-message" id="ocImportMessage"></p>
        </section>
      </aside>

      <main>
        <p class="archive-notice" id="archiveNotice"><strong>提示词与视觉资料库：</strong>输入服装、动作、构图、场景或画风关键词。找到合适内容后可以收藏并记录实测备注。</p>
        <div class="results-head"><h2 id="resultsTitle">提示词结果</h2><span id="status">可以开始</span></div>
        <div class="results" id="results"></div>
      </main>
    </div>
  </div>
  <script>
    const $ = (selector) => document.querySelector(selector);
    const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
    const formatNumber = (value) => new Intl.NumberFormat('zh-CN').format(value || 0);
    let currentMode = 'home';
    let currentResults = [];
    let currentCharacters = [];
    let tagDisplayLanguage = 'zh';
    const tagLabelCache = new Map();

    function displayCanonicalTag(tag) {
      const value = String(tag || '').trim();
      const item = tagLabelCache.get(value.toLowerCase());
      if (!item || tagDisplayLanguage === 'en') return value;
      return item.zh ? `${item.zh} (${item.en})` : item.en;
    }

    async function ensureTagLabels(tags) {
      const values = tags.map(value => String(value || '').trim()).filter(Boolean);
      const canonicalPattern = /^[A-Za-z0-9][A-Za-z0-9_()'./:+\- ]*$/;
      const missing = [...new Set(values)].filter(value => canonicalPattern.test(value) && !tagLabelCache.has(value.toLowerCase()));
      if (!missing.length) return false;
      let changed = false;
      for (let index = 0; index < missing.length; index += 500) {
        const response = await fetch('/api/tags/localize', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({tags:missing.slice(index,index+500), language:'zh'})});
        if (!response.ok) continue;
        const payload = await response.json();
        (payload.items || []).forEach(item => tagLabelCache.set(String(item.en).toLowerCase(), item));
        changed = true;
      }
      return changed;
    }

    function tagValuesFromItem(item) {
      return item.kind === 'tag' ? [item.title, ...String(item.content || '').split(',')] : [];
    }

    const kindLabels = {style:'画风',prompt:'完整提示词',modifier:'修饰词',wildcard:'通配词',caption:'图片说明',tag:'标签'};
    const safetyLabels = {sfw:'普通',suggestive:'轻度成人向',adult:'成人向','explicit-adult':'明确成人向',unrated:'尚未分级'};
    const modelFamilyLabels = {'danbooru-tags':'Booru 标签',anima:'Anima',krea2:'Krea 2'};
    const categoryLabels = {'web-capture':'网页资料','kisega-tag':'服装与物件标签'};

    function tagCardTitle(item) { return item.kind === 'tag' ? displayCanonicalTag(item.title) : item.title; }
    function tagCardContent(item) {
      if (item.kind !== 'tag') return item.content;
      return tagDisplayLanguage === 'zh' ? `标准英文输出：${item.content}` : item.content;
    }

    function setTagDisplayLanguage(language) {
      tagDisplayLanguage = language === 'en' ? 'en' : 'zh';
      $('#tagLanguageToggle').textContent = tagDisplayLanguage === 'zh' ? '标签：中英' : '标签：仅英文';
      window.dispatchEvent(new CustomEvent('tag-language-change', {detail:{language:tagDisplayLanguage}}));
      if (currentMode === 'prompts') searchPrompts().catch(console.error);
    }

    window.displayCanonicalTag = displayCanonicalTag;
    window.ensureTagLabels = ensureTagLabels;
    window.getTagDisplayLanguage = () => tagDisplayLanguage;
    window.toggleTagDisplayLanguage = () => setTagDisplayLanguage(tagDisplayLanguage === 'zh' ? 'en' : 'zh');

    function visualMarkup(item) {
      if (!item.visuals?.length) return '';
      const multiple = item.visuals.length > 1;
      const cards = item.visuals.map((visual, index) => {
        const rawVisualSafety = visual.safety || item.safety || 'unrated';
        const visualSafety = escapeHtml(rawVisualSafety);
        const openLabel = multiple ? `查看第 ${index + 1} 张 ↗` : '查看原图 ↗';
        return `<a class="visual-frame" href="${escapeHtml(visual.original_url)}" target="_blank" rel="noreferrer" aria-label="查看 ${escapeHtml(item.title)} 参照图 ${index + 1}">
          <img src="${escapeHtml(visual.thumbnail_url)}" alt="${escapeHtml(item.title)} 视觉参照 ${index + 1}" loading="lazy" decoding="async">
          <span class="visual-label">${openLabel}</span><span class="visual-safety ${visualSafety}">${escapeHtml(safetyLabels[rawVisualSafety] || '尚未分级')}</span>
        </a>`;
      }).join('');
      return `<div class="visual-gallery ${multiple ? 'multi' : ''}" style="--visual-count:${item.visuals.length}">${cards}</div>`;
    }

    function personalMarkup(item) {
      const rating = Number(item.user_rating || 0);
      const stars = [1, 2, 3, 4, 5].map(value => `<button class="star-button ${value <= rating ? 'active' : ''}" data-personal-action="rating" data-rating="${value}" aria-label="${value} 星" aria-pressed="${value === rating ? 'true' : 'false'}">★</button>`).join('');
      const note = item.user_note || '';
      return `<div class="personal-tools">
        <button class="favorite-button" data-personal-action="favorite" aria-pressed="${item.favorite ? 'true' : 'false'}">${item.favorite ? '★ 已收藏' : '☆ 收藏'}</button>
        <div class="rating-control" aria-label="个人评分">${stars}</div>
        <button class="note-button ${note ? 'has-note' : ''}" data-personal-action="note-toggle">${note ? '备注 ●' : '写备注'}</button>
      </div>
      ${note ? `<p class="note-preview">${escapeHtml(note)}</p>` : ''}
      <div class="note-editor" hidden><textarea maxlength="1200" placeholder="记录适用模型、构图效果或测试想法…">${escapeHtml(note)}</textarea><button class="save-note-button" data-personal-action="note-save">保存备注</button></div>`;
    }

    function characterCard(item, index) {
      const traits = [item.gender, item.age ? `${item.age}岁` : '', item.race, item.identity].filter(Boolean);
      const initial = Array.from(item.name || '?')[0] || '?';
      return `<article class="card character-card" data-character-index="${index}" style="animation-delay:${Math.min(index * 25, 250)}ms">
        <div class="character-mark" data-initial="${escapeHtml(initial)}"><span>OC Manager 本地副本</span><span>${escapeHtml(item.sheet_role === 'npc' ? '非玩家角色' : item.sheet_role === 'pc' ? '玩家角色' : item.sheet_role || '角色')}</span></div>
        <div class="card-meta">
          <span class="badge signal">角色</span>
          ${item.world ? `<span class="badge">${escapeHtml(item.world)}</span>` : ''}
          ${item.faction ? `<span class="badge soft">${escapeHtml(item.faction)}</span>` : ''}
        </div>
        <h3>${escapeHtml(item.name)}</h3>
        <p class="content">${escapeHtml(item.story_excerpt || '暂无故事简介')}</p>
        <div class="character-meta">
          <span><strong>角色资料</strong> ${escapeHtml(traits.join(' / ') || '未填写')}</span>
          <span><strong>提示词</strong> ${formatNumber(item.prompt_count)}</span>
          <span><strong>图片</strong> ${formatNumber(item.gallery_count)}</span>
          <span><strong>更新时间</strong> ${escapeHtml((item.source_updated_at || item.imported_at || '').slice(0, 10))}</span>
        </div>
        <div class="character-actions"><button class="character-create-button" data-character-create>以此角色开始创作</button><button class="detail-button" data-character-action="details" aria-expanded="false">展开角色资料 ↘</button></div>
        <div class="character-detail" hidden></div>
      </article>`;
    }

    function characterDetailMarkup(item) {
      const profile = item.profile || {};
      const prompts = item.prompts || [];
      const modules = Array.isArray(profile.modules) ? profile.modules : [];
      const timeline = Array.isArray(profile.timeline) ? profile.timeline : [];
      const relationships = Array.isArray(profile.relationships) ? profile.relationships : [];
      const gallery = Array.isArray(profile.gallery) ? profile.gallery : [];
      const promptMarkup = prompts.length ? prompts.map(prompt => `<div class="prompt-record"><strong>${escapeHtml(prompt.label || '未命名提示词')}</strong><p>${escapeHtml(prompt.text)}</p></div>`).join('') : '<p>这个角色还没有保存提示词。</p>';
      return `<h4>角色资料</h4>
        <p>${escapeHtml(item.story || '暂无故事内容')}</p>
        <div class="detail-counts"><span>${modules.length} 个模块</span><span>${timeline.length} 条时间线</span><span>${relationships.length} 组关系</span><span>${gallery.length} 张图片</span></div>
        <h4>角色提示词</h4>${promptMarkup}`;
    }

    async function loadStats() {
      const selectedSource = $('#source').value;
      const [stats, sources] = await Promise.all([fetch('/api/stats').then(r => r.json()), fetch('/api/sources').then(r => r.json())]);
      $('#entryCount').textContent = formatNumber(stats.entries);
      $('#sourceCount').textContent = formatNumber(stats.sources);
      $('#styleCount').textContent = formatNumber(stats.kinds?.style);
      $('#tagCount').textContent = formatNumber(stats.kinds?.tag);
      $('#favoriteCount').textContent = formatNumber(stats.personal?.favorites);
      $('#ocCount').textContent = formatNumber(stats.oc_manager?.characters);
      $('#homeEntryCount').textContent = formatNumber(stats.entries);
      $('#homeSourceCount').textContent = formatNumber(stats.sources);
      $('#homeOcCount').textContent = formatNumber(stats.oc_manager?.characters);
      $('#source').innerHTML = '<option value="">全部来源</option>' + sources.map(s => `<option value="${escapeHtml(s.source_id)}">${escapeHtml(s.name)}</option>`).join('');
      if ([...$('#source').options].some(option => option.value === selectedSource)) $('#source').value = selectedSource;
      $('#sourceList').innerHTML = '<p class="section-label">资料来源</p>' + sources.map(s => `<div class="source-row"><span>${escapeHtml(s.name)}</span><span>${formatNumber(s.entry_count)}</span></div>`).join('');
    }

    async function loadSourceSyncStatus() {
      const labels = {ready:'可以安全更新',dirty:'有本地改动',no_upstream:'没有上游',missing:'本地缺失',not_git:'不是 Git 仓库',failed:'检查失败'};
      const response = await fetch('/api/sources/sync-status');
      const sources = response.ok ? await response.json() : [];
      $('#sourceSyncList').innerHTML = sources.map(item => `<div class="source-sync-row"><strong>${escapeHtml(item.name)}</strong><span class="source-sync-state ${escapeHtml(item.status)}">${escapeHtml(labels[item.status] || item.status)}</span><code>${escapeHtml(item.branch || '—')} · ${escapeHtml((item.before || '').slice(0, 10) || '暂无版本')}</code></div>`).join('');
      const dirty = sources.filter(item => item.status === 'dirty').length;
      const ready = sources.filter(item => item.status === 'ready').length;
      $('#sourceSyncMessage').textContent = dirty ? `${dirty} 个资料源有本地改动，会自动跳过；其余 ${ready} 个可以安全更新。` : `${ready} 个资料源可以安全检查更新；只允许 fast-forward，不会覆盖本地修改。`;
    }

    async function loadOcWorlds() {
      const selectedWorld = $('#ocWorld').value;
      const worlds = await fetch('/api/oc-manager/worlds').then(r => r.json());
      $('#ocWorld').innerHTML = '<option value="">全部世界</option>' + worlds.map(world => `<option value="${escapeHtml(world.world_name)}">${escapeHtml(world.world_name)} · ${formatNumber(world.character_count)}</option>`).join('');
      if ([...$('#ocWorld').options].some(option => option.value === selectedWorld)) $('#ocWorld').value = selectedWorld;
    }

    async function searchPrompts() {
      $('#status').textContent = '正在查找…';
      $('#results').classList.remove('character-results');
      const params = new URLSearchParams({query: $('#query').value, kind: $('#kind').value, safety: $('#safety').value, source_id: $('#source').value, favorites_only: $('#favoritesOnly').getAttribute('aria-pressed'), limit: '30'});
      const data = await fetch('/api/search?' + params).then(r => r.json());
      currentResults = data.results;
      await ensureTagLabels(data.results.flatMap(tagValuesFromItem));
      $('#status').textContent = `找到 ${data.count} 条`;
      if (!data.results.length) {
        $('#results').innerHTML = '<div class="empty"><strong>没有找到对应资料</strong><span>换一个词，或放宽类型与内容分级。</span></div>';
        return;
      }
      $('#results').innerHTML = data.results.map((item, index) => `
        <article class="card ${item.favorite ? 'is-favorite' : ''}" data-result-index="${index}" style="animation-delay:${Math.min(index * 25, 250)}ms">
          ${visualMarkup(item)}
          <div class="card-meta">
            <span class="badge signal">${escapeHtml(kindLabels[item.kind] || '资料')}</span>
            <span class="badge">${escapeHtml(safetyLabels[item.safety] || '尚未分级')}</span>
            ${item.model_family ? `<span class="badge soft">${escapeHtml(modelFamilyLabels[item.model_family] || item.model_family)}</span>` : ''}
          </div>
          <h3>${escapeHtml(tagCardTitle(item))}</h3>
          <p class="content">${escapeHtml(tagCardContent(item))}</p>
          <div class="archive-add-tools"><select data-creative-slot aria-label="选择创作槽位"><option value="character">角色</option><option value="outfit">服装</option><option value="action">动作</option><option value="composition">构图</option><option value="scene">场景</option><option value="lighting">灯光</option><option value="style" ${item.kind === 'style' ? 'selected' : ''}>画风</option></select><button class="archive-add-button" data-creative-add>加入创作</button></div>
          ${personalMarkup(item)}
          <footer><span>${escapeHtml(item.source_name)} · ${escapeHtml(categoryLabels[item.category] || item.category || '未分类')}</span>${item.source_url ? `<a href="${escapeHtml(item.source_url)}" target="_blank" rel="noreferrer">查看来源 ↗</a>` : ''}</footer>
        </article>`).join('');
    }

    async function searchCharacters() {
      $('#status').textContent = '正在查找角色…';
      $('#results').classList.add('character-results');
      const params = new URLSearchParams({query: $('#query').value, world: $('#ocWorld').value, limit: '30'});
      const data = await fetch('/api/oc-manager/characters?' + params).then(r => r.json());
      currentCharacters = data.results;
      $('#status').textContent = `找到 ${data.count} 个角色`;
      if (!data.results.length) {
        $('#results').innerHTML = '<div class="empty"><strong>还没有找到角色</strong><span>可以换一个关键词，或选择 OC Manager 导出的 JSON 文件进行导入。</span></div>';
        return;
      }
      $('#results').innerHTML = data.results.map(characterCard).join('');
    }

    function runSearch() {
      return currentMode === 'characters' ? searchCharacters() : searchPrompts();
    }

    async function setMode(mode) {
      currentMode = mode;
      const characterMode = mode === 'characters';
      $('#promptFilters').hidden = characterMode;
      $('#ocFilters').hidden = !characterMode;
      $('#favoritesOnly').hidden = characterMode;
      $('#ocImportPanel').hidden = !characterMode;
      $('#resultsTitle').textContent = characterMode ? '角色结果' : '提示词结果';
      $('#query').placeholder = characterMode ? '角色名、世界、故事或外观' : '例如：哥特连衣裙、兔耳、逆光';
      $('#query').setAttribute('aria-label', characterMode ? '输入角色名、世界、故事或外观' : '输入提示词关键词');
      $('#searchButton').textContent = characterMode ? '查找角色' : '查找提示词';
      $('#searchLabel').textContent = characterMode ? '查找角色' : '查找提示词和视觉参考';
      $('#archiveNotice').innerHTML = characterMode ? '<strong>OC 角色库：</strong>导入 OC Manager JSON 后，可以按角色名、世界、故事和外观查找角色。' : '<strong>提示词与视觉资料库：</strong>输入服装、动作、构图、场景或画风关键词。找到合适内容后可以收藏并记录实测备注。';
      $('#query').value = '';
      if (characterMode) await loadOcWorlds();
      await runSearch();
    }

    async function setView(view) {
      const archiveMode = view === 'prompts' || view === 'characters';
      $('#homePage').hidden = view !== 'home';
      $('#creativePage').hidden = view !== 'creative';
      $('#discoveryPage').hidden = view !== 'discover';
      $('#workspacePage').hidden = view !== 'datasets';
      $('#loraPage').hidden = view !== 'lora';
      $('#comfyPage').hidden = view !== 'comfy';
      $('#remotePage').hidden = view !== 'remote';
      $('#managementPage').hidden = view !== 'management';
      $('#archiveWorkspace').hidden = !archiveMode;
      document.querySelectorAll('[data-view]').forEach(button => {
        if (button.classList.contains('app-nav-button')) {
          button.setAttribute('aria-current', button.dataset.view === view ? 'page' : 'false');
        }
      });
      if (archiveMode) {
        await setMode(view);
        $('#query').focus();
      } else if (view === 'creative' && window.ensureCreativeProject) {
        currentMode = view;
        await window.ensureCreativeProject();
      } else if (view === 'discover' && window.ensureHybridSearch) {
        currentMode = view;
        await window.ensureHybridSearch();
      } else if (view === 'datasets' && window.ensureDatasetWorkspace) {
        currentMode = view;
        await window.ensureDatasetWorkspace();
      } else if (view === 'lora' && window.ensureLoraProject) {
        currentMode = view;
        await window.ensureLoraProject();
      } else if (view === 'comfy' && window.ensureComfyResults) {
        currentMode = view;
        await window.ensureComfyResults();
      } else if (view === 'remote' && window.ensureRemoteDevices) {
        currentMode = view;
        await window.ensureRemoteDevices();
      } else if (view === 'management') {
        currentMode = view;
        await Promise.all([loadSourceSyncStatus(), window.ensureSourceCenter ? window.ensureSourceCenter() : Promise.resolve()]);
      } else {
        currentMode = view;
      }
      window.scrollTo({top: 0, behavior: 'smooth'});
    }
    window.setPromptHubView = setView;

    async function openExample() {
      await setView('prompts');
      $('#query').value = 'victorian military uniform';
      await searchPrompts();
    }

    async function importOcFile() {
      const file = $('#ocFile').files[0];
      if (!file) return;
      const button = $('#ocImportButton');
      button.disabled = true;
      button.textContent = '正在导入…';
      $('#ocImportMessage').textContent = '';
      try {
        const response = await fetch('/api/oc-manager/import?filename=' + encodeURIComponent(file.name), {method: 'POST', headers: {'Content-Type': 'application/json'}, body: file});
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || `导入失败: ${response.status}`);
        $('#ocImportMessage').textContent = `已导入 ${formatNumber(result.characters_imported)} 个角色 · ${formatNumber(result.worlds_imported)} 个世界`;
        await Promise.all([loadStats(), loadOcWorlds()]);
        await searchCharacters();
      } catch (error) {
        $('#ocImportMessage').textContent = `导入失败：${error.message}`;
      } finally {
        button.disabled = false;
        button.textContent = '导入到本地角色库';
      }
    }

    async function saveMark(item) {
      const response = await fetch('/api/marks', {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({source_id: item.source_id, external_id: item.external_id, favorite: Boolean(item.favorite), rating: item.user_rating || null, note: item.user_note || ''})
      });
      if (!response.ok) throw new Error(`保存失败: ${response.status}`);
      Object.assign(item, await response.json());
      $('#status').textContent = '收藏和备注已保存';
      await loadStats();
      await searchPrompts();
    }

    async function rebuild() {
      const button = $('#importButton');
      button.disabled = true;
      button.textContent = '正在重建索引…';
      try {
        const result = await fetch('/api/import', {method: 'POST'}).then(r => r.json());
        await loadStats();
        await searchPrompts();
        $('#status').textContent = `索引已更新，共 ${formatNumber(result.stats.entries)} 条资料`;
      } finally {
        button.disabled = false;
        button.textContent = '仅重建本地索引';
      }
    }

    async function syncPublicSources() {
      const button = $('#sourceSyncButton');
      button.disabled = true;
      button.textContent = '正在检查资料源…';
      try {
        const response = await fetch('/api/sources/sync', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{"source_ids":[]}'});
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || `启动更新失败：${response.status}`);
        let job = payload.job;
        while (['queued','running'].includes(job.status)) {
          $('#sourceSyncMessage').textContent = job.progress_message || '等待资料更新任务…';
          await new Promise(resolve => setTimeout(resolve, 500));
          job = await fetch(`/api/jobs/${encodeURIComponent(job.job_id)}`).then(result => result.json());
        }
        if (job.status !== 'completed') throw new Error(job.error || `资料更新${job.status}`);
        const result = job.result || {};
        $('#sourceSyncMessage').textContent = `更新完成：${result.updated || 0} 个有新版本，${result.unchanged || 0} 个已是最新，${result.skipped || 0} 个已安全跳过。`;
        await Promise.all([loadStats(), loadSourceSyncStatus()]);
      } catch (error) {
        $('#sourceSyncMessage').textContent = error.message;
      } finally {
        button.disabled = false;
        button.textContent = '↻ 更新公共提示词库';
      }
    }

    $('#searchButton').addEventListener('click', runSearch);
    $('#query').addEventListener('keydown', event => { if (event.key === 'Enter') runSearch(); });
    $('#kind').addEventListener('change', searchPrompts);
    $('#safety').addEventListener('change', searchPrompts);
    $('#source').addEventListener('change', searchPrompts);
    $('#ocWorld').addEventListener('change', searchCharacters);
    document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => setView(button.dataset.view)));
    document.querySelectorAll('[data-start]').forEach(button => button.addEventListener('click', () => setView(button.dataset.start)));
    $('#exampleButton').addEventListener('click', openExample);
    $('#ocFile').addEventListener('change', event => {
      const file = event.target.files[0];
      $('#ocFileName').textContent = file ? `${file.name} · ${(file.size / 1024).toFixed(1)} KiB` : '尚未选择文件';
      $('#ocImportButton').disabled = !file;
      $('#ocImportMessage').textContent = '';
    });
    $('#ocImportButton').addEventListener('click', importOcFile);
    $('#favoritesOnly').addEventListener('click', event => {
      const active = event.currentTarget.getAttribute('aria-pressed') === 'true';
      event.currentTarget.setAttribute('aria-pressed', String(!active));
      event.currentTarget.textContent = active ? '☆ 只看我的收藏' : '★ 正在只看收藏';
      searchPrompts();
    });
    $('#results').addEventListener('click', async event => {
      const characterButton = event.target.closest('[data-character-action="details"]');
      if (characterButton) {
        const card = characterButton.closest('.character-card');
        const item = currentCharacters[Number(card.dataset.characterIndex)];
        const detail = card.querySelector('.character-detail');
        const expanded = characterButton.getAttribute('aria-expanded') === 'true';
        if (expanded) {
          detail.hidden = true;
          characterButton.setAttribute('aria-expanded', 'false');
          characterButton.textContent = '展开角色资料 ↘';
          return;
        }
        characterButton.disabled = true;
        characterButton.textContent = '正在读取…';
        try {
          const response = await fetch('/api/oc-manager/characters/' + encodeURIComponent(item.character_id));
          if (!response.ok) throw new Error(`读取失败: ${response.status}`);
          detail.innerHTML = characterDetailMarkup(await response.json());
          detail.hidden = false;
          characterButton.setAttribute('aria-expanded', 'true');
          characterButton.textContent = '收起角色资料 ↗';
        } catch (error) {
          detail.textContent = error.message;
          detail.hidden = false;
          characterButton.textContent = '重新读取角色资料';
        } finally {
          characterButton.disabled = false;
        }
        return;
      }
      const actionButton = event.target.closest('[data-personal-action]');
      if (!actionButton) return;
      const card = actionButton.closest('.card');
      const item = currentResults[Number(card.dataset.resultIndex)];
      const action = actionButton.dataset.personalAction;
      if (action === 'note-toggle') {
        const editor = card.querySelector('.note-editor');
        editor.hidden = !editor.hidden;
        if (!editor.hidden) editor.querySelector('textarea').focus();
        return;
      }
      if (action === 'favorite') item.favorite = !item.favorite;
      if (action === 'rating') {
        const selected = Number(actionButton.dataset.rating);
        item.user_rating = item.user_rating === selected ? null : selected;
      }
      if (action === 'note-save') item.user_note = card.querySelector('textarea').value;
      try { await saveMark(item); } catch (error) { $('#status').textContent = '保存失败，请重试'; console.error(error); await searchPrompts(); }
    });
    $('#importButton').addEventListener('click', rebuild);
    $('#sourceSyncButton').addEventListener('click', syncPublicSources);
    window.loadPromptHubStats = loadStats;
    $('#tagLanguageToggle').addEventListener('click', window.toggleTagDisplayLanguage);
    Promise.all([loadStats(), loadOcWorlds(), searchPrompts()]).catch(error => { $('#status').textContent = '读取失败，请刷新页面'; console.error(error); });
  </script>
</body>
</html>
"""

INDEX_HTML = INDEX_HTML.replace(
    "</head>",
    f"{CREATIVE_STYLES}{WORKSPACE_STYLES}{LORA_STYLES}{COMFY_STYLES}{SEARCH_STYLES}{REMOTE_STYLES}{SOURCE_CENTER_STYLES}</head>",
    1,
)
INDEX_HTML = INDEX_HTML.replace(
    '<section class="management-page" id="managementPage" hidden>',
    f'{CREATIVE_HTML}{SEARCH_HTML}{WORKSPACE_HTML}{LORA_HTML}{COMFY_HTML}{REMOTE_HTML}<section class="management-page" id="managementPage" hidden>',
    1,
)
INDEX_HTML = INDEX_HTML.replace(
    '      </section>\n    </section>\n\n    <div class="workspace" id="archiveWorkspace" hidden>',
    f'      </section>\n{SOURCE_CENTER_HTML}\n    </section>\n\n    <div class="workspace" id="archiveWorkspace" hidden>',
    1,
)
INDEX_HTML = INDEX_HTML.replace(
    "</body>",
    f"{CREATIVE_SCRIPT}{SEARCH_SCRIPT}{WORKSPACE_SCRIPT}{LORA_SCRIPT}{COMFY_SCRIPT}{REMOTE_SCRIPT}{SOURCE_CENTER_SCRIPT}</body>",
    1,
)
