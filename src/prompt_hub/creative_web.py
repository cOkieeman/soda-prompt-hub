from __future__ import annotations

from prompt_hub.creative_web_layout import CREATIVE_HTML

__all__ = ["CREATIVE_HTML", "CREATIVE_SCRIPT", "CREATIVE_STYLES"]

CREATIVE_STYLES = r"""
<style>
  .creative-page { margin-top: 18px; border: 1px solid var(--line); background: var(--paper); box-shadow: 0 24px 70px rgba(39, 32, 22, .13); }
  .creative-page[hidden] { display: none; }
  .creative-heading { padding: 24px 28px; border-bottom: 1px solid var(--line); display: flex; justify-content: space-between; gap: 20px; align-items: end; background: linear-gradient(110deg, #ece5d5 0 72%, var(--acid) 72%); }
  .creative-heading h1 { margin: 4px 0 0; font: 700 clamp(38px, 5vw, 70px)/.88 "Iowan Old Style", serif; letter-spacing: -.05em; }
  .creative-heading p { margin: 0; max-width: 480px; font-size: 13px; color: var(--muted); }
  .creative-layout { display: grid; grid-template-columns: 250px minmax(430px, 1fr) 370px; min-height: 720px; }
  .project-rail, .output-rail { padding: 22px; background: #e7e0d0; }
  .project-rail { border-right: 1px solid var(--line); }
  .output-rail { border-left: 1px solid var(--line); background: var(--ink); color: #f4eddf; }
  .creative-editor { min-width: 0; padding: 26px; background-image: linear-gradient(rgba(31, 29, 25, .035) 1px, transparent 1px); background-size: 100% 36px; }
  .rail-button, .creative-action { width: 100%; border: 1px solid currentColor; padding: 11px 12px; text-align: left; font: 800 10px/1.2 monospace; letter-spacing: .06em; text-transform: uppercase; }
  .rail-button.primary { background: var(--signal); color: white; border-color: var(--signal); margin-bottom: 14px; }
  .project-list, .recipe-list { display: grid; gap: 7px; margin-top: 10px; }
  .project-item, .recipe-item { border: 1px solid rgba(31, 29, 25, .22); background: rgba(255,255,255,.35); padding: 10px; text-align: left; }
  .project-item.active { border-color: var(--signal); box-shadow: inset 3px 0 var(--signal); }
  .project-item strong, .recipe-item strong { display: block; font: 700 13px/1.25 "Avenir Next", sans-serif; }
  .project-item span, .recipe-item span { display: block; margin-top: 4px; color: var(--muted); font: 9px monospace; }
  .lineage-notice { margin: -7px 0 18px; border: 1px solid var(--signal); background: #eee4d2; padding: 10px 12px; color: var(--muted); font-size: 11px; }
  .lineage-notice[hidden] { display: none; }
  .lineage-notice strong { color: var(--signal); font: 800 10px monospace; }
  .lineage-notice a { margin-left: 8px; color: var(--signal); border-bottom: 1px solid currentColor; font: 800 9px monospace; }
  .iteration-panel { margin: 0 0 18px; border: 1px solid var(--line); background: #e9e1d1; box-shadow: inset 4px 0 var(--acid); }
  .iteration-panel[hidden] { display: none; }
  .iteration-panel-head { display: flex; justify-content: space-between; gap: 14px; padding: 14px 16px 10px; }
  .iteration-panel-head h2 { margin: 0; font: 700 24px "Iowan Old Style", serif; }
  .iteration-panel-head span { color: var(--muted); font: 9px monospace; }
  .iteration-summary { margin: 0; padding: 0 16px 12px; color: var(--muted); font-size: 11px; }
  .iteration-suggestions { margin: 0 16px 13px; padding-left: 18px; color: var(--ink); font-size: 11px; }
  .iteration-changes { display: grid; gap: 1px; border-top: 1px solid var(--line); background: var(--line); }
  .iteration-change { display: grid; grid-template-columns: 92px repeat(3, minmax(0, 1fr)); gap: 10px; padding: 11px 16px; background: #f6f0e4; }
  .iteration-change strong { font: 800 10px monospace; text-transform: uppercase; }
  .iteration-change div { min-width: 0; }
  .iteration-change label { display: block; margin-bottom: 3px; color: var(--muted); font: 8px monospace; text-transform: uppercase; }
  .iteration-change p { margin: 0; overflow-wrap: anywhere; font-size: 10px; line-height: 1.45; }
  .iteration-change .suggested { color: var(--signal); }
  .iteration-panel-actions { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 9px; align-items: center; padding: 12px 16px; }
  .iteration-panel-actions button { border: 1px solid var(--signal); background: var(--signal); color: white; padding: 9px 11px; text-align: left; font: 800 9px monospace; }
  .iteration-panel-actions button:disabled { border-color: rgba(31,29,25,.25); background: transparent; color: var(--muted); }
  .iteration-panel-actions p { margin: 0; color: var(--muted); font-size: 10px; }
  .rail-section { margin-top: 24px; padding-top: 18px; border-top: 1px solid rgba(31,29,25,.24); }
  .lm-status { margin: 8px 0; font-size: 11px; color: var(--muted); }
  .model-label { display: block; margin-bottom: 5px; color: var(--muted); font: 800 9px monospace; text-transform: uppercase; letter-spacing: .08em; }
  .model-select { width: 100%; border: 1px solid rgba(31,29,25,.22); background: rgba(255,255,255,.5); color: var(--ink); padding: 8px; font: 11px "Avenir Next", sans-serif; }

  .managed-model-list { display: grid; gap: 5px; margin-top: 8px; max-height: 240px; overflow-y: auto; }
  .managed-model-item { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 7px 9px; border: 1px solid rgba(31,29,25,.2); background: rgba(255,255,255,.4); font-size: 11px; color: var(--ink); }
  .managed-model-item span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .managed-model-item .mm-type { display: inline-block; margin-left: 6px; padding: 1px 5px; font: 8px monospace; border: 1px solid rgba(31,29,25,.25); color: var(--muted); }
  .managed-model-del { flex: 0 0 auto; width: 20px; height: 20px; border: 1px solid rgba(216,75,42,.5); background: transparent; color: var(--signal); font-size: 12px; line-height: 1; cursor: pointer; border-radius: 3px; transition: all .15s; }
  .managed-model-del:hover { background: var(--signal); color: #fff; }
  .managed-model-empty { color: var(--muted); font-size: 10px; padding: 6px 2px; }
  .project-head { display: grid; grid-template-columns: 1fr 180px; gap: 14px; margin-bottom: 18px; }
  .creative-field label, .slot-head label, .generation-grid label { display: block; margin-bottom: 6px; color: var(--muted); font: 800 9px monospace; text-transform: uppercase; letter-spacing: .08em; }
  .creative-field input, .creative-field textarea, .creative-field select, .slot-card textarea, .generation-grid input, .generation-grid textarea, .assist-select { width: 100%; border: 1px solid var(--line); background: rgba(248,244,235,.94); color: var(--ink); padding: 10px; font: 13px/1.5 "Avenir Next", sans-serif; }
  .creative-field textarea { min-height: 92px; resize: vertical; }
  .safety-note { margin: 7px 0 0; color: var(--muted); font-size: 10px; }
  .sourcing-panel { margin-top: 16px; border: 1px solid var(--line); background: #e9e1d1; box-shadow: inset 4px 0 var(--acid); }
  .sourcing-panel[hidden] { display: none; }
  .sourcing-panel-head { display: flex; justify-content: space-between; gap: 14px; align-items: start; padding: 15px 16px 10px; }
  .sourcing-panel-head h2 { margin: 0; font: 700 25px "Iowan Old Style", serif; }
  .sourcing-panel-head p { margin: 4px 0 0; color: var(--muted); font-size: 11px; }
  .sourcing-close { flex: 0 0 auto; border-bottom: 1px solid currentColor; font: 800 9px monospace; }
  .sourcing-status { margin: 0; padding: 0 16px 13px; color: var(--muted); font: 10px/1.5 monospace; }
  .sourcing-groups { display: grid; gap: 1px; background: var(--line); border-top: 1px solid var(--line); }
  .sourcing-group { min-width: 0; padding: 14px 16px 16px; background: #f4eddf; }
  .sourcing-group-head { display: flex; justify-content: space-between; gap: 14px; align-items: start; }
  .sourcing-group-head strong { font: 800 11px monospace; text-transform: uppercase; letter-spacing: .06em; }
  .sourcing-group-head span { color: var(--muted); font: 9px monospace; }
  .sourcing-queries { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 7px; }
  .query-chip { border: 1px solid rgba(31,29,25,.25); padding: 3px 6px; color: var(--muted); background: #eee5d5; font: 9px monospace; }
  .sourcing-candidates { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 10px; }
  .sourcing-card { min-width: 0; display: grid; grid-template-columns: 82px minmax(0, 1fr); border: 1px solid rgba(31,29,25,.28); background: #fbf7ef; }
  .sourcing-card.no-image { grid-template-columns: 1fr; }
  .sourcing-card img { width: 82px; height: 100%; min-height: 114px; object-fit: cover; border-right: 1px solid var(--line); }
  .sourcing-card-body { min-width: 0; display: flex; flex-direction: column; padding: 9px; }
  .sourcing-card-title { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 11px; }
  .sourcing-card-content { display: -webkit-box; overflow: hidden; margin: 5px 0 7px; color: var(--muted); font-size: 10px; line-height: 1.45; -webkit-line-clamp: 3; -webkit-box-orient: vertical; }
  .sourcing-card-meta { margin-top: auto; color: var(--muted); font: 8px/1.4 monospace; }
  .sourcing-add { margin-top: 7px; border: 1px solid var(--signal); color: var(--signal); padding: 6px 7px; text-align: left; font: 800 9px monospace; }
  .sourcing-add.is-added { color: var(--muted); border-color: rgba(31,29,25,.28); }
  .sourcing-empty { margin: 9px 0 0; color: var(--muted); font-size: 10px; }
  .slot-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 11px; }
  .slot-card { border: 1px solid var(--line); background: rgba(246,240,228,.92); padding: 13px; position: relative; }
  .slot-card:first-child { grid-column: 1 / -1; }
  .slot-card.is-locked { border-color: var(--signal); box-shadow: inset 0 3px var(--signal); }
  .slot-head { display: flex; justify-content: space-between; align-items: start; gap: 10px; }
  .slot-head small { display: block; color: var(--muted); font-size: 10px; margin-top: 2px; }
  .slot-lock { border: 1px solid var(--line); padding: 5px 7px; font: 800 9px monospace; }
  .slot-card.is-locked .slot-lock { background: var(--signal); color: white; border-color: var(--signal); }
  .slot-card textarea { min-height: 78px; resize: vertical; margin-top: 9px; }
  .creative-subsection { margin-top: 20px; padding-top: 17px; border-top: 1px solid var(--line); }
  .creative-subsection-head { display: flex; justify-content: space-between; gap: 12px; align-items: baseline; }
  .creative-subsection-head h2 { margin: 0; font: 700 24px "Iowan Old Style", serif; }
  .creative-subsection-head span { color: var(--muted); font: 9px monospace; }
  .reference-list { margin-top: 10px; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
  .reference-card { border: 1px solid var(--line); background: #f3ecdf; min-width: 0; }
  .reference-card img { width: 100%; aspect-ratio: 4/3; object-fit: cover; border-bottom: 1px solid var(--line); }
  .reference-card div { padding: 8px; }
  .reference-card strong { display: block; font-size: 11px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .reference-card span { color: var(--muted); font: 9px monospace; }
  .reference-remove { float: right; color: var(--signal); font: 800 9px monospace; }
  .reference-empty { color: var(--muted); font-size: 12px; padding: 18px; border: 1px dashed var(--line); grid-column: 1 / -1; }
  .result-review-tools { display: grid; grid-template-columns: minmax(0, 1fr) minmax(180px, .7fr) auto; gap: 8px; margin-top: 11px; align-items: end; }
  .result-review-tools label { min-width: 0; color: var(--muted); font: 800 9px monospace; text-transform: uppercase; }
  .result-review-tools input, .result-review-tools select { width: 100%; margin-top: 6px; border: 1px solid var(--line); background: #f7f1e5; padding: 9px; color: var(--ink); font: 10px monospace; }
  .result-review-tools button { height: 36px; background: var(--signal); color: white; padding: 0 12px; font: 800 9px monospace; }
  .result-review-status { margin: 8px 0 0; color: var(--muted); font-size: 10px; }
  .result-gallery { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin-top: 11px; }
  .result-card { min-width: 0; border: 1px solid var(--line); background: #f3ecdf; }
  .result-card.is-dataset-selected { border-color: var(--signal); box-shadow: inset 0 3px var(--acid); }
  .result-card img { width: 100%; aspect-ratio: 1; object-fit: cover; border-bottom: 1px solid var(--line); }
  .result-card-body { padding: 8px; }
  .result-card strong { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 10px; }
  .result-card span { display: block; margin-top: 4px; color: var(--muted); font: 8px monospace; }
  .result-card button { width: 100%; margin-top: 7px; border: 1px solid var(--signal); color: var(--signal); padding: 7px; text-align: left; font: 800 9px monospace; }
  .result-card .dataset-toggle.is-selected { background: var(--signal); color: white; }
  .dataset-caption { margin-top: 7px; border-top: 1px solid rgba(31,29,25,.2); padding-top: 7px; }
  .dataset-caption summary { cursor: pointer; color: var(--muted); font: 800 8px monospace; }
  .dataset-caption textarea { width: 100%; min-height: 78px; margin-top: 7px; resize: vertical; border: 1px solid var(--line); background: #fbf6ec; padding: 7px; color: var(--ink); font: 9px/1.45 monospace; }
  .wd14-toolbar { display: grid; grid-template-columns: minmax(0, 1fr) 110px 110px auto; gap: 9px; align-items: end; margin-top: 12px; border: 1px solid var(--line); background: #171714; color: #f4eddf; padding: 12px; box-shadow: inset 4px 0 var(--acid); }
  .wd14-toolbar strong { display: block; font: 800 10px monospace; letter-spacing: .06em; }
  .wd14-toolbar p { margin: 4px 0 0; color: #aaa395; font-size: 9px; }
  .wd14-toolbar label { color: #aaa395; font: 800 8px monospace; text-transform: uppercase; }
  .wd14-toolbar input { width: 100%; margin-top: 6px; border: 1px solid #706b61; background: #292824; color: #f4eddf; padding: 8px; font: 10px monospace; }
  .wd14-toolbar button { min-height: 34px; background: var(--acid); color: var(--ink); padding: 0 11px; font: 800 9px monospace; }
  .wd14-toolbar button:disabled { background: #383631; color: #777268; }
  .wd14-review { margin-top: 7px; border: 1px solid rgba(31,29,25,.26); background: #e9e1d1; padding: 7px; }
  .wd14-review summary { cursor: pointer; color: var(--signal); font: 800 8px monospace; }
  .wd14-review p { margin: 6px 0 0; color: var(--muted); font: 8px/1.45 monospace; overflow-wrap: anywhere; }
  .wd14-review textarea { width: 100%; min-height: 110px; margin-top: 7px; resize: vertical; border: 1px solid var(--line); background: #fbf6ec; padding: 7px; color: var(--ink); font: 9px/1.45 monospace; }
  .wd14-tag-locale { display: flex; justify-content: space-between; gap: 8px; align-items: center; margin-top: 8px; }
  .wd14-tag-locale span { color: var(--muted); font: 8px/1.4 monospace; }
  .wd14-tag-locale button { width: auto; margin: 0; padding: 5px 7px; }
  .wd14-tag-chips { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 8px; }
  .result-card .wd14-tag-chip { width: auto; margin: 0; border-color: rgba(31,29,25,.28); color: var(--muted); padding: 5px 6px; font: 8px/1.25 monospace; }
  .result-card .wd14-tag-chip.selected { border-color: var(--signal); background: var(--signal); color: white; }
  .wd14-advanced { margin-top: 8px; }
  .wd14-advanced summary { color: var(--muted); }
  .wd14-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 5px; }
  .result-card .wd14-actions button:last-child { background: var(--signal); color: white; }
  .result-card .wd14-run { border-color: #3f5250; color: #284b48; }
  .dataset-export-panel { display: grid; grid-template-columns: minmax(170px, .7fr) minmax(0, 1fr) auto; gap: 9px; align-items: end; margin-top: 12px; border: 1px solid var(--line); background: #e9e1d1; padding: 12px; box-shadow: inset 4px 0 var(--acid); }
  .dataset-export-panel label { color: var(--muted); font: 800 9px monospace; text-transform: uppercase; }
  .dataset-export-panel select { width: 100%; margin-top: 6px; border: 1px solid var(--line); background: #f7f1e5; padding: 9px; color: var(--ink); font: 10px monospace; }
  .dataset-export-panel p { margin: 0; color: var(--muted); font-size: 10px; }
  .dataset-export-panel button { min-height: 36px; background: var(--signal); color: white; padding: 0 12px; font: 800 9px monospace; }
  .dataset-export-panel button:disabled { background: transparent; border: 1px solid rgba(31,29,25,.25); color: var(--muted); }
  .review-proposal { margin-top: 12px; border: 1px solid var(--signal); background: #eee4d2; padding: 14px; box-shadow: inset 4px 0 var(--acid); }
  .review-proposal[hidden] { display: none; }
  .review-proposal-head { display: flex; justify-content: space-between; gap: 12px; }
  .review-proposal h3 { margin: 0; font: 700 22px "Iowan Old Style", serif; }
  .review-proposal-head span { color: var(--muted); font: 9px monospace; }
  .review-summary { margin: 9px 0; font-size: 12px; line-height: 1.55; }
  .review-slot-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px; }
  .review-slot { border: 1px solid rgba(31,29,25,.23); background: rgba(255,255,255,.38); padding: 8px; }
  .review-slot strong { display: block; color: var(--signal); font: 800 9px monospace; }
  .review-slot p { margin: 5px 0 0; font-size: 10px; line-height: 1.45; }
  .review-slot span { display: block; margin-top: 5px; color: var(--muted); font: 8px monospace; }
  .review-findings { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 7px; margin-top: 10px; }
  .review-finding { border-top: 1px solid var(--line); padding-top: 7px; }
  .review-finding strong { font: 800 9px monospace; }
  .review-finding ul { margin: 6px 0 0; padding-left: 15px; font-size: 10px; line-height: 1.5; }
  .review-prompts { margin-top: 10px; }
  .review-prompts summary { cursor: pointer; color: var(--signal); font: 800 9px monospace; }
  .review-prompts pre { max-height: 210px; overflow: auto; white-space: pre-wrap; border: 1px solid var(--line); background: #f8f1e4; padding: 9px; font: 9px/1.5 monospace; }
  .review-warning { color: #9a3023; font-size: 10px; }
  .review-actions { display: grid; grid-template-columns: 1.25fr 1.1fr 1fr auto; gap: 6px; margin-top: 11px; }
  .review-actions button { border: 1px solid var(--ink); padding: 8px; text-align: left; font: 800 9px monospace; }
  .review-actions .primary { background: var(--signal); border-color: var(--signal); color: white; }
  .generation-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 10px; }
  .generation-grid .wide { grid-column: 1 / -1; }
  .generation-grid textarea { min-height: 65px; resize: vertical; }
  .output-profile-tabs { display: grid; grid-template-columns: 1fr 1fr; border: 1px solid rgba(244,237,223,.45); margin-bottom: 16px; }
  .profile-tab { padding: 10px; color: #f4eddf; font: 800 10px monospace; }
  .profile-tab.active { background: var(--acid); color: var(--ink); }
  .output-block { margin-top: 18px; }
  .output-block header { display: flex; justify-content: space-between; align-items: center; gap: 10px; }
  .output-block h3 { margin: 0 0 7px; color: var(--acid); font: 800 10px monospace; text-transform: uppercase; }
  .output-copy { color: #f4eddf; border-bottom: 1px solid currentColor; font: 800 9px monospace; }
  .output-text { min-height: 128px; max-height: 260px; overflow: auto; white-space: pre-wrap; margin: 0; padding: 12px; border: 1px solid rgba(244,237,223,.28); color: #f4eddf; background: rgba(255,255,255,.04); font: 12px/1.65 monospace; }
  .output-negative { min-height: 88px; color: #dbbfad; }
  .warning-list { margin: 14px 0 0; padding: 0; list-style: none; }
  .warning-list li { margin-top: 6px; padding-left: 13px; color: #d8cdbd; font-size: 11px; position: relative; }
  .warning-list li::before { content: "!"; color: var(--acid); position: absolute; left: 0; font: 800 10px monospace; }
  .workflow-dispatch { margin-top: 18px; padding: 12px; border: 1px solid rgba(244,237,223,.38); background: rgba(255,255,255,.045); }
  .workflow-dispatch-head { display: flex; justify-content: space-between; gap: 10px; color: #f4eddf; }
  .workflow-dispatch-head strong { font: 800 10px monospace; letter-spacing: .05em; }
  .workflow-dispatch-head span { color: var(--acid); font: 800 9px monospace; }
  .workflow-dispatch > label { display: block; margin-top: 11px; color: #b9ae9f; font: 800 8px monospace; text-transform: uppercase; }
  .workflow-dispatch select { width: 100%; margin-top: 6px; border: 1px solid rgba(244,237,223,.38); background: #292824; color: #f4eddf; padding: 9px; font: 9px monospace; }
  .workflow-dispatch .workflow-cost { display: flex; gap: 8px; align-items: start; text-transform: none; }
  .workflow-cost input { margin-top: 2px; accent-color: var(--acid); }
  .workflow-cost span, .workflow-cost strong, .workflow-cost small { display: block; }
  .workflow-cost strong { color: #f4eddf; font: 800 9px monospace; }
  .workflow-cost small { margin-top: 3px; color: #aaa395; font: 9px/1.4 "Avenir Next", sans-serif; }
  .workflow-dispatch .creative-action { width: 100%; margin-top: 12px; }
  .workflow-dispatch p { margin: 8px 0 0; color: #b9ae9f; font: 9px/1.45 monospace; overflow-wrap: anywhere; }
  .workflow-task-link { margin-top: 8px; color: var(--acid); border-bottom: 1px solid currentColor; font: 800 8px monospace; }
  .output-actions { display: grid; gap: 8px; margin-top: 22px; }
  .output-actions .creative-action { color: #f4eddf; }
  .output-actions .creative-action.primary { background: var(--acid); color: var(--ink); border-color: var(--acid); }
  .save-state { margin-top: 10px; color: #b9ae9f; font: 9px monospace; text-transform: uppercase; }
  .assist-proposal { margin-top: 12px; padding: 10px; border: 1px solid var(--signal); background: #f4ecdc; }
  .assist-proposal pre { max-height: 180px; overflow: auto; white-space: pre-wrap; font: 10px/1.5 monospace; }
  .assist-proposal-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
  .archive-add-tools { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 6px; margin-top: 12px; }
  .archive-add-tools select { min-width: 0; border: 1px solid var(--line); background: #f5f0e4; padding: 8px; font: 10px monospace; }
  .archive-add-button, .character-create-button { background: var(--signal); color: white; padding: 8px 10px; font: 800 9px monospace; }
  .character-actions { display: flex; flex-wrap: wrap; gap: 7px; }
  .recipe-name { width: 100%; margin-top: 12px; border: 1px solid rgba(244,237,223,.35); background: rgba(255,255,255,.06); color: #f4eddf; padding: 9px; }
  @media (max-width: 1180px) { .creative-layout { grid-template-columns: 220px minmax(0, 1fr); } .output-rail { grid-column: 1 / -1; border-left: 0; border-top: 1px solid var(--line); } }
  @media (max-width: 760px) { .creative-heading { display: block; background: #ece5d5; } .creative-heading p { margin-top: 12px; } .creative-layout { display: block; } .project-rail { border-right: 0; border-bottom: 1px solid var(--line); } .slot-grid, .project-head, .result-review-tools, .review-slot-grid, .review-findings, .review-actions, .iteration-change, .iteration-panel-actions, .dataset-export-panel, .wd14-toolbar { grid-template-columns: 1fr; } .slot-card:first-child { grid-column: auto; } .reference-list, .sourcing-candidates, .result-gallery { grid-template-columns: 1fr; } .generation-grid { grid-template-columns: 1fr 1fr; } }

/* API Configuration Section */
.api-config-section { margin-top: 24px; padding: 16px; border: 1px solid rgba(244,241,234,0.15); border-radius: 6px; background: rgba(31,36,33,0.4); }
.api-config-head { margin-bottom: 12px; }
.api-config-head h3 { margin: 0; font-size: 14px; font-weight: 600; color: #f4f1ea; }
.api-config-label { display: block; margin-bottom: 12px; font-size: 12px; color: #b9ae9f; }

  /* Combobox 样式 */
  .combobox-wrapper { position: relative; display: flex; }
  .combobox-input { 
  flex: 1; 
  padding: 10px 40px 10px 12px; 
  border: 1px solid var(--line); 
  border-radius: 6px; 
  font: 14px "Inter", sans-serif; 
  color: var(--ink); 
  background: #E8E8E8 !important;
  transition: all 0.2s;
  }
  .combobox-input:focus { 
  outline: none; 
  border-color: #C4612F; 
  box-shadow: 0 0 0 3px rgba(196, 97, 47, 0.1);
  }
  .combobox-trigger {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--muted);
  transition: all 0.2s;
  border-radius: 4px;
  }
  .combobox-trigger:hover { background: rgba(0,0,0,0.05); color: var(--ink); }
  .combobox-dropdown {
  display: none;
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  right: 0;
  background: #2A2F2E;
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.3);
  max-height: 400px;
  overflow-y: auto;
  z-index: 9999;
  opacity: 0;
  pointer-events: none;
  transform: translateY(-10px);
  transition: opacity 0.2s, transform 0.2s;
  }
  .combobox-dropdown.is-open {
  display: block;
  opacity: 1;
  pointer-events: auto;
  transform: translateY(0);
  }
  .combobox-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  cursor: pointer;
  border-bottom: 1px solid rgba(231,225,215,0.4);
  transition: background 0.15s;
  position: relative;
  }
  .combobox-option:last-child { border-bottom: none; }
  .combobox-option:hover { background: var(--surface); }
  .combobox-option.is-selected::before {
  content: "✓";
  position: absolute;
  left: -4px;
  color: #3B82F6;
  font-weight: 600;
  font-size: 16px;
  }
  .combobox-option.is-selected .option-name { color: #3B82F6; font-weight: 500; }
  .option-name { 
  font: 14px "Inter", sans-serif; 
  font-weight: 400;
  color: var(--ink);
  margin-left: 20px;
  }
  .option-url { 
  font: 12px "SF Mono", Consolas, monospace; 
  color: var(--muted);
  text-align: right;
  max-width: 60%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  }
  .combobox-option-custom .option-url { font-family: "Inter", sans-serif; font-style: italic; }

  .api-vision-toggle { padding: 4px 8px; border: 1px solid rgba(244,241,234,0.25); background: transparent; color: #b9ae9f; font-size: 11px; cursor: pointer; border-radius: 3px; transition: all .15s; }
  .api-vision-toggle:hover { border-color: rgba(196,97,47,0.5); color: #f4f1ea; }
  .api-vision-toggle.is-vision { background: rgba(215,228,85,0.15); border-color: var(--acid); color: var(--acid); }
</style>
"""

CREATIVE_SCRIPT = r"""
<script>
(function() {
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => [...document.querySelectorAll(sel)];

  const slotsMeta = {
    character: ['角色', '人物名、瞳色与稳定特征'], outfit: ['服装', '衣物、材质、配饰与穿着方式'],
    action: ['动作', '姿态、手部动作、表情与互动'], composition: ['构图', '景别、机位、视角与主体位置'],
    scene: ['场景', '地点、环境物件、天气与时间'], lighting: ['灯光', '光向、色温、明暗与氛围'], style: ['画风', '媒介、审美、质感、LoRA 与风格词']
  };
  const creativeState = {project: null, projects: [], recipes: [], outputs: {}, profile: 'anima', workflowProfiles: [], workflowMessage: '', workflowMessageProjectId: '', datasetProfile: 'anima', datasetMessage: '', datasetMessageProjectId: '', suggestion: null, sourcing: null, sourcingProjectId: '', sourcingRun: 0, review: null, reviewAssetId: '', reviewProjectId: '', iteration: null, iterationProjectId: '', iterationRun: 0, iterationMessage: '', iterationMessageProjectId: '', visionAvailable: false, saveTimer: null, compileTimer: null, loadedMeta: false};

  async function creativeJson(url, options = {}) {
    const response = await fetch(url, options);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || `Request failed: ${response.status}`);
    return data;
  }

  function slotTemplate() {
    return Object.entries(slotsMeta).map(([key, meta]) => `<div class="slot-card" data-slot-card="${key}"><div class="slot-head"><div><label>${meta[0]}</label><small>${meta[1]}</small></div><button class="slot-lock" data-lock-slot="${key}" aria-pressed="false">UNLOCKED</button></div><textarea data-slot-input="${key}" placeholder="填写 ${meta[0]} 内容…"></textarea></div>`).join('');
  }

  function blankProject() {
    return {title:'未命名绘图项目', brief_zh:'', safety_mode:'sfw', target_profile:'anima', character_id:'', slots:Object.fromEntries(Object.keys(slotsMeta).map(k => [k, ''])), slot_locks:Object.fromEntries(Object.keys(slotsMeta).map(k => [k, false])), references:[], generation:{}, lineage:{}, test_notes:''};
  }

  function iterationOf(project) { const value = Number(project?.lineage?.iteration); return Number.isInteger(value) && value > 0 ? value : 1; }

  function collectCreative() {
    if (!creativeState.project) return blankProject();
    const generation = {...(creativeState.project.generation || {}),
      steps: Number($('#genSteps').value) || null, cfg: Number($('#genCfg').value) || null, seed: $('#genSeed').value.trim(),
      result_images: $('#genResults').value.split('\n').map(v => v.trim()).filter(Boolean)
    };
    return {...creativeState.project, title:$('#creativeTitle').value.trim() || '未命名绘图项目', brief_zh:$('#creativeBrief').value.trim(), safety_mode:$('#creativeSafety').value, target_profile:creativeState.profile, slots:Object.fromEntries([...document.querySelectorAll('[data-slot-input]')].map(el => [el.dataset.slotInput, el.value.trim()])), generation, test_notes:$('#creativeNotes').value.trim()};
  }

  function renderCreativeProject() {
    const project = creativeState.project;
    if (!project) return;
    $('#creativeTitle').value = project.title || '';
    $('#creativeBrief').value = project.brief_zh || '';
    $('#creativeSafety').value = project.safety_mode || 'sfw';
    $('#creativeNotes').value = project.test_notes || '';
    $('#genSteps').value = project.generation?.steps ?? '';
    $('#genCfg').value = project.generation?.cfg ?? '';
    $('#genSeed').value = project.generation?.seed ?? '';
    $('#genResults').value = (project.generation?.result_images || []).join('\n');
    Object.keys(slotsMeta).forEach(key => {
      const input = document.querySelector(`[data-slot-input="${key}"]`); const card = document.querySelector(`[data-slot-card="${key}"]`); const lock = document.querySelector(`[data-lock-slot="${key}"]`);
      input.value = project.slots?.[key] || ''; const locked = Boolean(project.slot_locks?.[key]); card.classList.toggle('is-locked', locked); lock.setAttribute('aria-pressed', String(locked)); lock.textContent = locked ? 'LOCKED' : 'UNLOCKED';
    });
    creativeState.profile = project.target_profile || creativeState.profile;
    document.querySelectorAll('[data-profile]').forEach(button => button.classList.toggle('active', button.dataset.profile === creativeState.profile));
    renderCreativeReferences(); renderCreativeProjects(); renderLineageNotice(); renderIterationPanel(); renderSourcing(); renderResultGallery(); renderReviewProposal(); renderWorkflowProfiles(); $('#creativeSaveState').textContent = `项目已加载 · V${iterationOf(project)} · R${project.revision || 1}`; compileCreative().catch(showCreativeError); loadIterationContext().catch(showCreativeError);
  }

  function renderCreativeProjects() {
    $('#creativeProjectList').innerHTML = creativeState.projects.length ? creativeState.projects.map(project => { const iteration = iterationOf(project); const parent = Number(project.lineage?.parent_iteration); const origin = parent > 0 ? ` · 来自 V${parent}` : ''; return `<button class="project-item ${creativeState.project?.project_id === project.project_id ? 'active' : ''}" data-project-id="${escapeHtml(project.project_id)}"><strong>${escapeHtml(project.title)}</strong><span>V${iteration} · R${project.revision}${origin}<br>${escapeHtml((project.updated_at || '').slice(0,16).replace('T',' '))}</span></button>`; }).join('') : '<p class="lm-status">还没有项目。</p>';
  }

  function renderLineageNotice() {
    const notice = $('#lineageNotice'); const project = creativeState.project; const lineage = project?.lineage || {}; const iteration = iterationOf(project);
    if (iteration <= 1 || !lineage.parent_project_id) { notice.hidden = true; notice.textContent = ''; return; }
    const source = lineage.source_asset_filename || '上一轮结果图'; const parent = Number(lineage.parent_iteration) || iteration - 1;
    const sourceUrl = lineage.source_asset_id ? `/result-media/${encodeURIComponent(lineage.parent_project_id)}/original/${encodeURIComponent(lineage.source_asset_id)}` : '';
    notice.hidden = false; notice.innerHTML = `<strong>VERSION V${iteration}</strong> · 基于 V${parent} 的 ${escapeHtml(source)} 创建。旧项目和旧结果图保持不变。${sourceUrl ? `<a href="${sourceUrl}" target="_blank" rel="noreferrer">查看来源图</a>` : ''}`;
  }

  function renderIterationPanel() {
    const panel = $('#iterationPanel'); const project = creativeState.project; const iteration = iterationOf(project);
    if (iteration <= 1 || !project?.lineage?.parent_project_id) { panel.hidden = true; return; }
    panel.hidden = false; $('#iterationVersion').textContent = `V${Number(project.lineage.parent_iteration) || iteration - 1} → V${iteration}`;
    const context = creativeState.iterationProjectId === project.project_id ? creativeState.iteration : null;
    if (!context) { $('#iterationSummary').textContent = '正在读取上一版与复盘建议…'; $('#iterationSuggestions').innerHTML = ''; $('#iterationChanges').innerHTML = ''; $('#iterationStatus').textContent = '正在建立版本对照…'; $('#applyIterationSuggestions').disabled = true; $('#applyIterationSuggestions').textContent = '暂无可应用建议'; return; }
    const review = context.review || {}; $('#iterationSummary').textContent = review.summary_zh || '这一轮没有保存复盘摘要。';
    $('#iterationSuggestions').innerHTML = (review.improvements || []).map(item => `<li>${escapeHtml(item)}</li>`).join('') || '<li>这一轮没有结构化改进建议。</li>';
    const visibleChanges = (context.changes || []).filter(item => item.status !== 'unchanged' || (item.suggested && item.suggested !== item.current));
    const statusLabels = {changed:'已修改',added:'本轮新增',removed:'本轮留空',unchanged:'尚未修改',unknown:'上一版不可用'};
    $('#iterationChanges').innerHTML = visibleChanges.length ? visibleChanges.map(item => { const meta = slotsMeta[item.slot] || [item.slot]; const state = item.locked ? ' · 已锁定' : item.applicable ? ' · 可填入建议' : ''; return `<article class="iteration-change"><strong>${escapeHtml(meta[0])}<br>${escapeHtml(statusLabels[item.status] || item.status)}${state}</strong><div><label>上一版</label><p>${escapeHtml(item.previous || '—')}</p></div><div><label>当前版</label><p>${escapeHtml(item.current || '—')}</p></div><div class="suggested"><label>复盘观察</label><p>${escapeHtml(item.suggested || '—')}</p></div></article>`; }).join('') : '<p class="reference-empty" style="background:#f6f0e4;margin:0;padding:14px 16px">当前槽位与上一版一致，也没有可显示的槽位建议。</p>';
    const count = (context.applicable_slots || []).length; const button = $('#applyIterationSuggestions'); button.disabled = count === 0; button.textContent = count ? `确认填入 ${count} 个空槽位` : '没有可直接填入的建议';
    const savedMessage = creativeState.iterationMessageProjectId === project.project_id ? creativeState.iterationMessage : '';
    $('#iterationStatus').textContent = savedMessage || (context.parent_available ? '只会填入空且未锁定槽位，已有内容不会被替换。' : '上一版项目不可用；仍可查看 lineage 中保存的复盘建议。');
  }

  async function loadIterationContext() {
    const project = creativeState.project; const runId = ++creativeState.iterationRun;
    if (!project?.project_id || iterationOf(project) <= 1 || !project.lineage?.parent_project_id) { creativeState.iteration = null; creativeState.iterationProjectId = ''; renderIterationPanel(); return; }
    const context = await creativeJson(`/api/creative/projects/${encodeURIComponent(project.project_id)}/iteration`);
    if (runId !== creativeState.iterationRun || creativeState.project?.project_id !== project.project_id) return;
    creativeState.iteration = context; creativeState.iterationProjectId = project.project_id; renderIterationPanel();
  }

  function renderCreativeReferences() {
    const refs = creativeState.project?.references || [];
    $('#creativeReferences').innerHTML = refs.length ? refs.map((ref, index) => { const visual = ref.visuals?.[0]; return `<article class="reference-card">${visual ? `<img src="${escapeHtml(visual.thumbnail_url)}" alt="${escapeHtml(ref.title)}">` : ''}<div><button class="reference-remove" data-remove-reference="${index}">REMOVE</button><strong>${escapeHtml(ref.title || '未命名参考')}</strong><span>${escapeHtml(ref.slot || ref.kind || 'reference')}</span></div></article>`; }).join('') : '<p class="reference-empty">还没有参考资料。去“提示词库”找到卡片后，选择槽位并点击“加入创作”。</p>';
  }

  function renderResultGallery() {
    const assets = creativeState.project?.generation?.result_assets || [];
    const profileLabel = creativeState.datasetProfile === 'anima' ? 'Anima tags' : 'Krea 2 自然语言';
    $('#datasetProfile').value = creativeState.datasetProfile;
    $('#resultGallery').innerHTML = assets.length ? assets.map(asset => renderResultCard(asset, profileLabel)).join('') : '<p class="reference-empty">还没有导入结果图。你可以从 Windows、共享目录或下载文件中选择 PNG、JPEG、WebP。</p>';
    const selectedCount = assets.filter(asset => asset.dataset_selected === true).length;
    $('#exportDataset').disabled = selectedCount === 0;
    $('#tagSelectedDataset').disabled = selectedCount === 0 || selectedCount > 24;
    const savedMessage = creativeState.datasetMessageProjectId === creativeState.project?.project_id ? creativeState.datasetMessage : '';
    $('#datasetExportStatus').textContent = savedMessage || (selectedCount > 24 ? `已精选 ${selectedCount} 张；同步 WD14 每次最多 24 张，导出不受影响。` : selectedCount ? `已精选 ${selectedCount} 张；将按 ${profileLabel} 生成同名 caption。` : '先在上方手动精选结果图；导出不会改动原图。');
    const localeTags = assets.flatMap(asset => { const tagging = asset.wd14_tagging || {}; return [...(tagging.general || []).map(item => item.tag), ...(tagging.characters || []).map(item => item.tag), ...String(tagging.draft_tags || '').split(',')]; }).filter(Boolean);
    if (window.ensureTagLabels && localeTags.length) window.ensureTagLabels(localeTags).then(changed => { if (changed) renderResultGallery(); }).catch(console.error);
  }

  function renderResultCard(asset, profileLabel) {
    const selected = asset.dataset_selected === true; const captions = asset.dataset_captions || {}; const caption = captions[creativeState.datasetProfile] || '';
    return `<article class="result-card ${selected ? 'is-dataset-selected' : ''}"><a href="${escapeHtml(asset.original_url)}" target="_blank" rel="noreferrer"><img src="${escapeHtml(asset.thumbnail_url)}" alt="${escapeHtml(asset.filename || '本地结果图')}" loading="lazy"></a><div class="result-card-body"><strong>${escapeHtml(asset.filename || '本地结果图')}</strong><span>${Number(asset.width) || '?'} × ${Number(asset.height) || '?'} · ${escapeHtml(asset.safety || 'sfw')}</span><button class="dataset-toggle ${selected ? 'is-selected' : ''}" data-dataset-toggle="${escapeHtml(asset.asset_id)}">${selected ? '✓ 已加入数据集' : '＋ 加入数据集'}</button><button class="wd14-run" data-wd14-tag="${escapeHtml(asset.asset_id)}">${asset.wd14_tagging ? '重新运行 WD14' : 'WD14 自动打标'}</button>${renderWd14Review(asset)}<details class="dataset-caption"><summary>${profileLabel} caption · 留空使用项目输出</summary><textarea data-dataset-caption="${escapeHtml(asset.asset_id)}" maxlength="12000" placeholder="留空时自动采用当前项目的 ${profileLabel} positive prompt">${escapeHtml(caption)}</textarea><button data-save-caption="${escapeHtml(asset.asset_id)}">保存此图 caption</button></details><button data-review-asset="${escapeHtml(asset.asset_id)}" ${creativeState.visionAvailable ? '' : 'disabled'}>${creativeState.visionAvailable ? '用本地模型复盘' : '暂无视觉模型'}</button></div></article>`;
  }

  function renderWd14Review(asset) {
    const tagging = asset.wd14_tagging; if (!tagging) return '';
    const rating = tagging.rating?.tag || 'unknown'; const ratingScore = Number(tagging.rating?.score); const characters = (tagging.characters || []).map(item => item.tag).filter(Boolean);
    const draft = tagging.draft_tags || ''; const draftValues = draft.split(',').map(value => value.trim()).filter(Boolean); const selectedTags = new Set(draftValues.map(value => value.toLowerCase())); const candidates = [...new Set([...(tagging.general || []).map(item => item.tag).filter(Boolean), ...draftValues])]; const animaCaption = asset.dataset_captions?.anima || ''; const confirmed = Boolean(tagging.confirmed_at) && animaCaption === draft;
    const state = confirmed ? '已确认到 Anima caption' : tagging.confirmed_at ? 'Anima caption 后续已修改' : '尚未确认';
    const chips = candidates.map(tag => `<button class="wd14-tag-chip ${selectedTags.has(tag.toLowerCase()) ? 'selected' : ''}" data-wd14-chip="${escapeHtml(asset.asset_id)}" data-tag-value="${escapeHtml(tag)}" aria-pressed="${selectedTags.has(tag.toLowerCase())}">${escapeHtml(window.displayCanonicalTag ? window.displayCanonicalTag(tag) : tag)}</button>`).join('');
    const language = window.getTagDisplayLanguage?.() === 'en' ? 'TAGS: EN' : '标签：中英';
    const characterLabels = characters.map(tag => window.displayCanonicalTag ? window.displayCanonicalTag(tag) : tag);
    return `<details class="wd14-review" open><summary>WD14 草稿 · ${escapeHtml(rating)} ${Number.isFinite(ratingScore) ? Math.round(ratingScore * 100) + '%' : ''} · ${state}</summary><p>角色候选：${escapeHtml(characterLabels.join(', ') || '无（原创 OC 常见）')}<br>General ${Number(tagging.general_threshold).toFixed(2)} · Character ${Number(tagging.character_threshold).toFixed(2)} · ${escapeHtml(tagging.provider || 'CPU')}</p><div class="wd14-tag-locale"><span>点击标签保留或移除；保存和导出始终使用英文 tag。</span><button data-toggle-tag-language>${language}</button></div><div class="wd14-tag-chips">${chips}</div><details class="wd14-advanced"><summary>高级英文编辑</summary><textarea data-wd14-draft="${escapeHtml(asset.asset_id)}" maxlength="12000" aria-label="WD14 Anima 标签草稿">${escapeHtml(draft)}</textarea></details><div class="wd14-actions"><button data-save-wd14="${escapeHtml(asset.asset_id)}">保存审核草稿</button><button data-confirm-wd14="${escapeHtml(asset.asset_id)}">确认用作 Anima caption</button></div></details>`;
  }

  function toggleWd14Chip(assetId, tag) {
    const asset = (creativeState.project?.generation?.result_assets || []).find(item => item.asset_id === assetId); if (!asset?.wd14_tagging) return;
    const values = String(asset.wd14_tagging.draft_tags || '').split(',').map(value => value.trim()).filter(Boolean); const key = tag.toLowerCase(); const exists = values.some(value => value.toLowerCase() === key); asset.wd14_tagging.draft_tags = (exists ? values.filter(value => value.toLowerCase() !== key) : [...values, tag]).join(', '); renderResultGallery();
  }

  function updateVisionHint() {
    const select = $('#visionModel'); const option = select.options[select.selectedIndex];
    if (!creativeState.visionAvailable || !option) { $('#resultModelHint').textContent = '暂无可用视觉模型，请先在上方 External API 配置中拉取并保存视觉模型。'; return; }
    const loaded = option.textContent.trim().startsWith('●');
    $('#resultModelHint').textContent = loaded
      ? '● 当前视觉模型已加载，可以直接复盘。'
      : '○ 当前视觉模型已选择，可直接用于复盘。';
  }

  function renderReviewProposal() {
    const proposal = $('#reviewProposal'); const review = creativeState.review;
    if (!review || creativeState.reviewProjectId !== creativeState.project?.project_id) { proposal.hidden = true; return; }
    proposal.hidden = false; $('#reviewModelName').textContent = review.model || '本地视觉模型'; $('#reviewSummary').textContent = review.summary_zh || '模型没有提供摘要。';
    const current = collectCreative();
    $('#reviewSlots').innerHTML = Object.entries(slotsMeta).map(([slot, meta]) => { const value = review.observed_slots?.[slot] || ''; const state = current.slot_locks?.[slot] ? '已锁定，不写回' : current.slots?.[slot] ? '已有内容，仅展示' : '空槽位，可确认补充'; return `<article class="review-slot"><strong>${meta[0]} / ${slot}</strong><p>${escapeHtml(value || '未识别到明确内容')}</p><span>${state}</span></article>`; }).join('');
    const findingMeta = [['strengths','优点'],['issues','问题'],['improvements','下一轮建议']];
    $('#reviewFindings').innerHTML = findingMeta.map(([key,label]) => `<section class="review-finding"><strong>${label}</strong><ul>${(review[key] || []).map(item => `<li>${escapeHtml(item)}</li>`).join('') || '<li>无</li>'}</ul></section>`).join('');
    const prompts = review.reconstructed_prompts || {};
    $('#reviewPrompts').textContent = `ANIMA POSITIVE\n${prompts.anima_positive || ''}\n\nANIMA NEGATIVE\n${prompts.anima_negative || ''}\n\nKREA 2 POSITIVE\n${prompts.krea2_positive || ''}\n\nKREA 2 AVOID\n${prompts.krea2_avoid || ''}`;
    $('#reviewWarning').hidden = !review.safety_warning; $('#reviewWarning').textContent = review.safety_warning ? `安全提示：${review.safety_warning}` : '';
  }

  function referenceKey(item, slot) {
    return `${item.source_id}:${item.external_id}:${slot}`;
  }

  function renderSourcing() {
    const result = creativeState.sourcing;
    const panel = $('#sourcingPanel');
    if (!result || creativeState.sourcingProjectId !== creativeState.project?.project_id) { panel.hidden = true; return; }
    panel.hidden = false;
    const references = collectCreative().references || [];
    const groups = Object.entries(slotsMeta).map(([slot, meta]) => {
      const group = result.slots?.[slot] || {locked:false, queries:[], candidates:[]};
      const queries = (group.queries || []).map(query => `<span class="query-chip">${escapeHtml(query)}</span>`).join('');
      const candidates = (group.candidates || []).map((item, index) => {
        const visual = item.visuals?.[0]; const added = references.some(ref => ref.key === referenceKey(item, slot));
        return `<article class="sourcing-card ${visual ? '' : 'no-image'}">${visual ? `<img src="${escapeHtml(visual.thumbnail_url)}" alt="${escapeHtml(item.title || meta[0])}">` : ''}<div class="sourcing-card-body"><strong class="sourcing-card-title">${escapeHtml(item.title || item.content || '未命名资料')}</strong><p class="sourcing-card-content">${escapeHtml(item.content || item.title || '')}</p><span class="sourcing-card-meta">${escapeHtml(item.match_reason || item.kind || '')}<br>命中：${escapeHtml(item.match_query || '')} · ${escapeHtml(item.safety || 'sfw')}</span><button class="sourcing-add ${added ? 'is-added' : ''}" data-source-slot="${slot}" data-source-index="${index}">${added ? '✓ 已加入，可再次查看' : `＋ 加入${meta[0]}槽位`}</button></div></article>`;
      }).join('');
      const empty = group.locked ? '此槽位已锁定，本轮不检索。' : (group.queries || []).length ? '本轮没有找到足够相关的本地资料。' : '没有识别出这个槽位的检索词；可先手动补充槽位内容。';
      return `<section class="sourcing-group"><div class="sourcing-group-head"><strong>${meta[0]} / ${slot}</strong><span>${group.locked ? 'LOCKED' : `${(group.candidates || []).length} 条候选`}</span></div>${queries ? `<div class="sourcing-queries">${queries}</div>` : ''}${candidates ? `<div class="sourcing-candidates">${candidates}</div>` : `<p class="sourcing-empty">${empty}</p>`}</section>`;
    }).join('');
    $('#sourcingGroups').innerHTML = groups;
  }

  function renderCreativeRecipes() {
    $('#creativeRecipeList').innerHTML = creativeState.recipes.length ? creativeState.recipes.map(recipe => `<button class="recipe-item" data-recipe-id="${escapeHtml(recipe.recipe_id)}"><strong>${escapeHtml(recipe.name)}</strong><span>${escapeHtml((recipe.updated_at || '').slice(0,10))} · ${escapeHtml(recipe.snapshot?.project?.safety_mode || 'sfw')}</span></button>`).join('') : '<p class="lm-status">还没有保存配方。</p>';
  }

  function renderOutput() {
    const output = creativeState.outputs[creativeState.profile] || {};
    $('#creativePositive').textContent = output.positive || '先填写一个槽位。';
    $('#creativeNegative').textContent = output.negative || '';
    $('#creativeWarnings').innerHTML = (output.warnings || []).map(w => `<li>${escapeHtml(w)}</li>`).join('');
  }

  function matchingWorkflowProfiles() {
    return creativeState.workflowProfiles.filter(profile => profile.model_family === creativeState.profile);
  }

  function renderWorkflowProfiles() {
    const select = $('#workflowProfile'); const profiles = matchingWorkflowProfiles(); const previous = select.value;
    select.innerHTML = profiles.map(profile => `<option value="${escapeHtml(profile.profile_id)}">${escapeHtml(profile.label)} · ${profile.node_count} nodes</option>`).join('');
    if (profiles.some(profile => profile.profile_id === previous)) select.value = previous;
    const selected = profiles.find(profile => profile.profile_id === select.value) || profiles[0];
    $('#sendWorkflow').disabled = !selected || !creativeState.project?.project_id;
    const currentMessage = creativeState.workflowMessageProjectId === creativeState.project?.project_id ? creativeState.workflowMessage : '';
    if (currentMessage) { $('#workflowRunStatus').textContent = currentMessage; return; }
    if (!selected) { $('#workflowRunStatus').textContent = `尚未导入 ${creativeState.profile === 'anima' ? 'Anima' : 'Krea 2'} Workflow Profile。`; return; }
    const omitted = (selected.low_cost_omits || []).join('、');
    $('#workflowRunStatus').textContent = omitted ? `低成本模式会跳过：${omitted}。` : '使用当前项目 Prompt 与生成参数投递。';
  }

  async function compileCreative() {
    if (!creativeState.project) return;
    const payload = collectCreative();
    const [anima, krea2] = await Promise.all(['anima','krea2'].map(profile_id => creativeJson('/api/creative/compile', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({...payload, profile_id})})));
    creativeState.outputs = {anima, krea2}; renderOutput();
  }

  function queueCreativeSave() {
    if (!creativeState.project) return;
    creativeState.iterationMessage = ''; creativeState.iterationMessageProjectId = '';
    $('#creativeSaveState').textContent = '等待自动保存…';
    clearTimeout(creativeState.saveTimer);
    clearTimeout(creativeState.compileTimer);
    creativeState.saveTimer = setTimeout(() => saveCreative().catch(showCreativeError), 650);
    creativeState.compileTimer = setTimeout(() => compileCreative().catch(showCreativeError), 160);
  }

  async function saveCreative() {
    if (!creativeState.project?.project_id) return;
    $('#creativeSaveState').textContent = '正在保存到本机…';
    creativeState.project = await creativeJson('/api/creative/projects/' + encodeURIComponent(creativeState.project.project_id), {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(collectCreative())});
    const index = creativeState.projects.findIndex(p => p.project_id === creativeState.project.project_id);
    if (index >= 0) creativeState.projects[index] = creativeState.project; else creativeState.projects.unshift(creativeState.project);
    renderCreativeProjects(); $('#creativeSaveState').textContent = `已保存 · R${creativeState.project.revision}`; await loadIterationContext();
  }

  async function sendWorkflowProfile() {
    if (!creativeState.project?.project_id) throw new Error('请先建立一个创作项目');
    await saveCreative(); await compileCreative();
    const profileId = $('#workflowProfile').value;
    if (!profileId) throw new Error('当前模型类型还没有可用 Workflow Profile');
    const button = $('#sendWorkflow'); button.disabled = true; button.textContent = '正在投递…';
    creativeState.workflowMessageProjectId = creativeState.project.project_id;
    creativeState.workflowMessage = '正在把生成包保存到 Mac，并发送到 5060 Ti…'; renderWorkflowProfiles();
    try {
      const result = await creativeJson(`/api/workflow-profiles/${encodeURIComponent(profileId)}/tasks`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({project_id:creativeState.project.project_id, low_cost:$('#workflowLowCost').checked})});
      creativeState.workflowMessage = `已投递 ${result.profile.label} · ${result.task.task_id} · ${result.node_count} nodes；到“设备连接”查看回传。`;
    } catch (error) {
      creativeState.workflowMessage = `投递失败：${error.message}`;
      throw error;
    } finally {
      button.textContent = '发送到 5060 Ti'; renderWorkflowProfiles();
    }
  }

  async function createCreativeProject(seed = {}) {
    clearTimeout(creativeState.saveTimer);
    if (creativeState.project?.project_id) await saveCreative();
    const project = await creativeJson('/api/creative/projects', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({...blankProject(), ...seed})});
    creativeState.project = project; creativeState.sourcing = null; creativeState.sourcingProjectId = ''; creativeState.review = null; creativeState.reviewProjectId = ''; creativeState.projects.unshift(project); renderCreativeProject(); $('#creativeSaveState').textContent = '新项目已保存到本机 · R1'; return project;
  }

  async function loadCreativeMeta() {
    const [projects, recipes, models, workflowProfiles] = await Promise.all([creativeJson('/api/creative/projects'), creativeJson('/api/creative/recipes'), creativeJson('/api/local-models'), creativeJson('/api/workflow-profiles')]);
      // Load unified model list
      const unifiedModels = await creativeJson('/api/models/list').catch(() => ({success:false,models:[],text_models:[],vision_models:[]}));
    creativeState.projects = projects; creativeState.recipes = recipes; renderCreativeProjects(); renderCreativeRecipes();
      // Populate unified model selectors
      if (unifiedModels.success && unifiedModels.models.length > 0) {
        const textSelect = $('#textModelSelect');
        const visionSelect = $('#visionModelSelect');
        if (unifiedModels.text_models.length) {
          textSelect.innerHTML = unifiedModels.text_models.map(m => `<option value="${escapeHtml(m.id)}">${escapeHtml(m.id)}${m.provider ? ' · ' + escapeHtml(m.provider) : ''}</option>`).join('');
        } else {
          textSelect.innerHTML = `<option value="" disabled selected>还未添加模型</option>`;
        }
        if (unifiedModels.vision_models.length) {
          visionSelect.innerHTML = unifiedModels.vision_models.map(m => `<option value="${escapeHtml(m.id)}">${escapeHtml(m.id)}${m.provider ? ' · ' + escapeHtml(m.provider) : ''}</option>`).join('');
        } else {
          visionSelect.innerHTML = `<option value="" disabled selected>还未添加模型</option>`;
        }
        // Set defaults
        const defaultText = unifiedModels.text_models.find(m => m.id.includes('lm-studio')) || unifiedModels.text_models[0];
        const defaultVision = unifiedModels.vision_models.find(m => m.id.includes('lm-studio')) || unifiedModels.vision_models[0];
        if (defaultText) textSelect.value = defaultText.id;
        if (defaultVision) visionSelect.value = defaultVision.id;
      }
    creativeState.workflowProfiles = workflowProfiles; renderWorkflowProfiles(); renderManagedModelList(unifiedModels);
    // 本地辅助下拉框：使用统一模型（含外接），文本模型
    const assistSelect = $('#lmModel');
    const assistModels = unifiedModels.success && unifiedModels.text_models.length ? unifiedModels.text_models : (models.models || []);
    if (assistModels.length) {
      assistSelect.innerHTML = assistModels.map(model => `<option value="${escapeHtml(model.id)}">${escapeHtml(model.name || model.id)}${model.provider ? ` · ${escapeHtml(model.provider)}` : ''}</option>`).join('');
      assistSelect.value = assistModels[0].id;
      $('#lmStatus').textContent = `已加载 ${assistModels.length} 个文本模型`;
    } else {
      assistSelect.innerHTML = `<option value="" disabled selected>还未添加模型</option>`;
      assistSelect.disabled = true;
      $('#lmStatus').textContent = '还未添加文本模型，请先在下方 External API 配置中添加';
    }

    // 结果图复盘视觉模型下拉框：使用统一模型（含外接），视觉模型
    const visionModelSelect = $('#visionModel');
    const unifiedVision = unifiedModels.success && unifiedModels.vision_models.length ? unifiedModels.vision_models : [];
    if (unifiedVision.length) {
      visionModelSelect.innerHTML = unifiedVision.map(model => `<option value="${escapeHtml(model.id)}">${escapeHtml(model.name || model.id)}${model.provider ? ` · ${escapeHtml(model.provider)}` : ''}</option>`).join('');
      visionModelSelect.value = unifiedVision[0].id;
    } else {
      visionModelSelect.innerHTML = `<option value="" disabled selected>还未添加模型</option>`;
    }
    creativeState.visionAvailable = Boolean(unifiedModels.success && unifiedVision.length);
    visionModelSelect.disabled = !creativeState.visionAvailable;
    $('#resultModelHint').textContent = creativeState.visionAvailable ? `已加载 ${unifiedVision.length} 个视觉模型` : '暂无可用视觉模型，请先在上方配置并保存视觉模型';
  }

  // API Configuration Management
  let fetchedModels = [];
  let existingModelIds = new Set();
  let pendingAdditions = new Map(); // modelId -> {url, key, vision}

  // Load existing models
  async function loadExistingModels() {
    try {
      const response = await fetch('/api/models/config');
      if (response.ok) {
        const config = await response.json();
        existingModelIds = new Set((config.models || []).map(m => m.id));
      }
    } catch (error) {
      console.warn('Failed to load existing models:', error);
    }
  }

  // Handle preset selection
  

  // Fetch models from API
  $('#fetchModelsBtn').addEventListener('click', async () => {
    const baseUrl = $('#apiBaseUrl').value.trim();
    const apiKey = $('#apiKey').value.trim();
    
    if (!baseUrl) {
      alert('请先填写 Base URL');
      return;
    }
    if (!apiKey) {
      alert('请先填写 API Key');
      return;
    }

    $('#fetchModelsBtn').textContent = '拉取中...';
    $('#fetchModelsBtn').disabled = true;

    try {
      const response = await fetch(`${baseUrl}/models`, {
        headers: { 'Authorization': `Bearer ${apiKey}` }
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      fetchedModels = data.data || data.models || [];
      
      if (fetchedModels.length === 0) {
        $('#apiFetchedModelList').innerHTML = '<p class="api-empty-hint">未获取到任何模型</p>';
      } else {
        renderFetchedModels();
      }
    } catch (error) {
      alert(`拉取失败: ${error.message}`);
      $('#apiFetchedModelList').innerHTML = '<p class="api-empty-hint" style="color:#c4612f;">拉取失败，请检查 URL 和 Key</p>';
    } finally {
      $('#fetchModelsBtn').textContent = '拉取模型列表';
      $('#fetchModelsBtn').disabled = false;
    }
  });

  function renderFetchedModels() {
    const container = $('#apiFetchedModelList');
    const baseUrl = $('#apiBaseUrl').value.trim();
    const apiKey = $('#apiKey').value.trim();

    container.innerHTML = fetchedModels.map(model => {
      const modelId = model.id || model.name;
      const isAdded = existingModelIds.has(modelId);
      const isPending = pendingAdditions.has(modelId);

      if (isAdded) {
        return `
          <div class="api-fetched-model">
            <span class="api-model-name-text">${escapeHtml(modelId)}</span>
            <span class="api-added-label">已添加</span>
          </div>`;
      }

      return `
        <div class="api-fetched-model" data-model-id="${escapeHtml(modelId)}">
          <span class="api-model-name-text">${escapeHtml(modelId)}</span>
          <div class="api-model-actions">
            <button type="button" class="api-vision-toggle" data-vision="0" data-model-id="${escapeHtml(modelId)}">设为视觉</button>
            <button class="api-add-btn" data-model-id="${escapeHtml(modelId)}">+</button>
          </div>
        </div>`;
    }).join('');

    // Bind vision toggle buttons
    container.querySelectorAll('.api-vision-toggle').forEach(toggle => {
      toggle.addEventListener('click', () => {
        const isVision = toggle.dataset.vision === '1';
        toggle.dataset.vision = isVision ? '0' : '1';
        toggle.textContent = isVision ? '设为视觉' : '视觉模型 ✓';
        toggle.classList.toggle('is-vision', !isVision);
      });
    });

    // Bind add buttons
    container.querySelectorAll('.api-add-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const modelId = btn.dataset.modelId;
        const row = btn.closest('.api-fetched-model');
        const visionCheckbox = row ? row.querySelector('.vision-checkbox') : null;
        const supportsVision = visionCheckbox ? visionCheckbox.checked : false;

        pendingAdditions.set(modelId, {
          id: modelId,
          model_name: modelId,
          base_url: baseUrl,
          api_key: apiKey,
          supports_vision: supportsVision,
          provider: 'custom'
        });

        // Update button to show pending
        btn.textContent = '待保存';
        btn.style.background = 'rgba(185,174,159,0.3)';
        btn.style.color = '#7a7267';
        btn.disabled = true;
      });
    });
  }

  // Save configuration
  $('#saveApiConfigBtn').addEventListener('click', async () => {
    // 收集所有待保存（已点 + 的）按钮对应的模型，不依赖 pendingAdditions
    const pendingBtns = [...document.querySelectorAll('#apiFetchedModelList .api-add-btn')];
    const newModels = pendingBtns.map(btn => {
      const mid = btn.dataset.modelId;
      const row = btn.closest('.api-fetched-model');
      const visionToggle = row ? row.querySelector('.api-vision-toggle') : null;
      return {
        id: mid,
        model_name: mid,
        base_url: $('#apiBaseUrl').value.trim(),
        api_key: $('#apiKey').value.trim(),
        supports_vision: visionToggle ? visionToggle.dataset.vision === '1' : false,
        provider: 'custom'
      };
    });

    if (newModels.length === 0) {
      alert('请先点击模型右侧的 + 按钮添加');
      return;
    }

    $('#saveApiConfigBtn').textContent = '保存中...';
    $('#saveApiConfigBtn').disabled = true;

    try {
      // Load existing config
      const response = await fetch('/api/models/config');
      let config = { models: [] };
      if (response.ok) {
        config = await response.json();
      }
      config.models = [...(config.models || []), ...newModels];

      // Save
      const saveResponse = await fetch('/api/models/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });

      if (!saveResponse.ok) {
        throw new Error('保存失败');
      }

      alert(`成功添加 ${newModels.length} 个模型`);
      
      // Clear pending and refresh
      pendingAdditions.clear();
      await loadExistingModels();
      renderFetchedModels();

      // Reload model dropdowns
      await loadCreativeMeta();

    } catch (error) {
      alert(`保存失败: ${error.message}`);
    } finally {
      $('#saveApiConfigBtn').textContent = '保存配置';
      $('#saveApiConfigBtn').disabled = false;
    }
  });

  // Initialize
  loadExistingModels();
  loadCreativeMeta();


  function renderManagedModelList(unifiedModels) {
    const container = $('#managedModelList');
    if (!container) return;
    const all = (unifiedModels && unifiedModels.models) || [];
    if (!all.length) {
      container.innerHTML = '<div class="managed-model-empty">还未添加模型</div>';
      return;
    }
    container.innerHTML = all.map(m => `
      <div class="managed-model-item" data-model-id="${escapeHtml(m.id)}">
        <span>${escapeHtml(m.name || m.id)}<span class="mm-type">${escapeHtml(m.provider || '')}</span></span>
        <button class="managed-model-del" data-del-model="${escapeHtml(m.id)}" title="删除此模型">×</button>
      </div>`).join('');

    container.querySelectorAll('.managed-model-del').forEach(btn => {
      btn.addEventListener('click', () => deleteManagedModel(btn.dataset.delModel));
    });
  }

  async function deleteManagedModel(modelId) {
    if (!modelId) return;
    if (!confirm(`确定删除模型 ${modelId} 吗？此操作会从已管理模型中移除。`)) return;
    try {
      const response = await fetch('/api/models/config/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: modelId })
      });
      const result = await response.json();
      if (result.success) {
        await loadCreativeMeta();
      } else {
        alert(`删除失败: ${result.error || '未知错误'}`);
      }
    } catch (error) {
      alert(`删除失败: ${error.message}`);
    }
  }

  function initCombobox() {
    const comboboxInput = document.getElementById('apiBaseUrl');
    const comboboxTrigger = document.getElementById('comboboxTrigger');
    const comboboxDropdown = document.getElementById('comboboxDropdown');
    if (!comboboxInput || !comboboxTrigger || !comboboxDropdown) return;
    const comboboxOptions = comboboxDropdown.querySelectorAll('.combobox-option');
    let currentSelectedUrl = '';
    function updateSelection(url) {
      currentSelectedUrl = url;
      comboboxOptions.forEach(opt => opt.classList.toggle('is-selected', opt.dataset.url === url));
    }
    comboboxTrigger.addEventListener('click', (e) => {
      e.stopPropagation();
      comboboxDropdown.classList.toggle('is-open');
    });
    comboboxOptions.forEach(option => {
      option.addEventListener('click', (e) => {
        e.stopPropagation();
        const url = option.dataset.url;
        const name = option.dataset.name;
        if (name === '自定义') { comboboxInput.value = ''; comboboxInput.focus(); }
        else { comboboxInput.value = url; updateSelection(url); }
        comboboxDropdown.classList.remove('is-open');
      });
    });
    comboboxInput.addEventListener('input', () => updateSelection(comboboxInput.value));
    document.addEventListener('click', () => comboboxDropdown.classList.remove('is-open'));
    comboboxInput.addEventListener('click', (e) => e.stopPropagation());
    setTimeout(() => { if (comboboxInput.value) updateSelection(comboboxInput.value); }, 100);
  }
  if (document.readyState !== 'loading') initCombobox();
  else document.addEventListener('DOMContentLoaded', initCombobox);

})();
</script>
"""
