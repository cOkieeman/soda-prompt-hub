from __future__ import annotations

from prompt_hub.creative_web_layout import CREATIVE_HTML

__all__ = ["CREATIVE_HTML", "CREATIVE_SCRIPT", "CREATIVE_STYLES"]

CREATIVE_STYLES = r"""
<style>
  .creative-page { margin-top: 18px; border: 1px solid var(--line); background: var(--paper); box-shadow: 0 24px 70px rgba(39, 32, 22, .13); }
  #creativePage .eyebrow, #creativePage .section-label, #creativePage label, #creativePage .rail-button, #creativePage .creative-action, #creativePage .output-block h3, #creativePage .sourcing-group-head strong, #creativePage .save-state { text-transform: none; }
  .creative-page[hidden] { display: none; }
  .creative-heading { padding: 24px 28px; border-bottom: 1px solid var(--line); display: flex; justify-content: space-between; gap: 20px; align-items: end; background: linear-gradient(110deg, #ece5d5 0 72%, var(--acid) 72%); }
  .creative-heading h1 { margin: 4px 0 0; font: 700 clamp(38px, 5vw, 70px)/.88 "Iowan Old Style", serif; letter-spacing: -.05em; }
  .creative-heading p { margin: 0; max-width: 480px; font-size: 13px; color: var(--muted); }
  .creative-layout { display: grid; grid-template-columns: 250px minmax(430px, 1fr) 370px; min-height: 720px; }
  .project-rail, .output-rail { padding: 22px; background: #e7e0d0; }
  .project-rail { border-right: 1px solid var(--line); }
  .output-rail { border-left: 1px solid var(--line); background: var(--ink); color: #f4eddf; }
  .creative-editor { min-width: 0; padding: 26px; background-image: linear-gradient(rgba(31, 29, 25, .035) 1px, transparent 1px); background-size: 100% 36px; }
  .rail-button, .creative-action { width: 100%; border: 1px solid currentColor; background: transparent; padding: 11px 12px; text-align: left; font: 800 10px/1.2 monospace; letter-spacing: .06em; text-transform: uppercase; }
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
  .external-model-settings { margin-top: 14px; border: 1px solid rgba(31,29,25,.24); background: rgba(255,255,255,.28); }
  .external-model-settings > summary { cursor: pointer; padding: 10px; color: var(--signal); font: 800 10px/1.3 monospace; }
  .external-model-settings[open] > summary { border-bottom: 1px solid rgba(31,29,25,.2); }
  .external-model-settings > p { margin: 10px; color: var(--muted); font-size: 10px; line-height: 1.5; }
  .external-model-settings > label { display: grid; gap: 4px; margin: 9px 10px; color: var(--muted); font: 800 8px/1.3 monospace; }
  .external-model-settings input { min-width: 0; width: 100%; border: 1px solid rgba(31,29,25,.28); background: #f7f1e5; padding: 8px; color: var(--ink); font: 10px/1.4 monospace; }
  .external-model-settings .external-model-check { display: flex; align-items: center; gap: 7px; }
  .external-model-check input { width: auto; accent-color: var(--signal); }
  .external-model-button { width: calc(100% - 20px); margin: 5px 10px; border: 1px solid var(--signal); padding: 8px; color: var(--signal); text-align: left; font: 800 9px/1.3 monospace; }
  .external-model-button.primary { background: var(--signal); color: white; }
  .external-model-button:disabled { border-color: rgba(31,29,25,.25); background: transparent; color: var(--muted); }
  .external-model-status { margin: 9px 10px !important; color: var(--muted); font-size: 9px !important; line-height: 1.45; overflow-wrap: anywhere; }
  .external-model-candidates, .external-model-list { display: grid; gap: 5px; margin: 8px 10px; max-height: 190px; overflow-y: auto; }
  .external-model-candidate, .external-model-item { display: grid; grid-template-columns: minmax(0,1fr) auto; gap: 6px; align-items: center; border: 1px solid rgba(31,29,25,.2); background: rgba(255,255,255,.35); padding: 7px; }
  .external-model-candidate span, .external-model-item span { min-width: 0; overflow: hidden; text-overflow: ellipsis; font: 9px/1.35 monospace; }
  .external-model-candidate button, .external-model-item button { border: 1px solid rgba(31,29,25,.3); padding: 5px 6px; color: var(--signal); font: 800 8px monospace; }
  .external-model-item-actions { display: flex; gap: 4px; }
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
  .profile-tab { border: 0; background: transparent; padding: 10px; color: #f4eddf; font: 800 10px monospace; }
  .profile-tab.active { background: var(--acid); color: var(--ink); }
  .output-block { margin-top: 18px; }
  .output-block-head { display: flex; justify-content: space-between; align-items: center; gap: 10px; }
  .output-block h3 { margin: 0 0 7px; color: var(--acid); font: 800 10px monospace; text-transform: uppercase; }
  .output-copy { border: 0; border-bottom: 1px solid currentColor; background: transparent; padding: 3px 0; color: #f4eddf; font: 800 9px monospace; cursor: pointer; }
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
  .workflow-dispatch select, .workflow-dispatch input[type=number] { width: 100%; margin-top: 6px; border: 1px solid rgba(244,237,223,.38); background: #292824; color: #f4eddf; padding: 9px; font: 9px monospace; }
  .workflow-dispatch .workflow-cost { display: flex; gap: 8px; align-items: start; text-transform: none; }
  .workflow-cost input { margin-top: 2px; accent-color: var(--acid); }
  .workflow-cost span, .workflow-cost strong, .workflow-cost small { display: block; }
  .workflow-cost strong { color: #f4eddf; font: 800 9px monospace; }
  .workflow-cost small { margin-top: 3px; color: #aaa395; font: 9px/1.4 "Avenir Next", sans-serif; }
  .workflow-dispatch .creative-action { width: 100%; margin-top: 12px; }
  .workflow-dispatch p { margin: 8px 0 0; color: #b9ae9f; font: 9px/1.45 monospace; overflow-wrap: anywhere; }
  .workflow-controls { margin-top: 10px; border-top: 1px solid rgba(244,237,223,.22); padding-top: 9px; }
  .workflow-controls summary { cursor: pointer; color: var(--acid); font: 800 9px monospace; }
  .workflow-control-list { display: grid; gap: 8px; margin-top: 10px; }
  .workflow-control-list label, .workflow-pair label, .workflow-lora-row label { display: grid; gap: 4px; color: #b9ae9f; font: 800 8px monospace; text-transform: uppercase; }
  .workflow-model-card { display: grid; grid-template-columns: minmax(0,1fr) 88px; gap: 7px; align-items: stretch; }
  .workflow-model-card > label { align-content: end; }
  .workflow-model-visual { display: grid; min-height: 78px; border: 1px solid rgba(244,237,223,.32); background: repeating-linear-gradient(135deg,#302f2b 0 8px,#35342f 8px 9px); color: #aaa395; }
  .workflow-model-preview { position: relative; display: block; min-height: 78px; overflow: hidden; }
  .workflow-model-preview img { width: 100%; height: 100%; min-height: 78px; object-fit: cover; transition: transform .2s ease; }
  .workflow-model-preview:hover img { transform: scale(1.035); }
  .workflow-model-preview span { position: absolute; inset: auto 5px 5px; background: rgba(20,19,17,.8); color: #f4eddf; padding: 4px 5px; font: 700 7px monospace; }
  .workflow-civitai-link { display: block; border-top: 1px solid rgba(244,237,223,.22); padding: 5px 6px; color: var(--acid); font: 800 7px/1.35 monospace; text-align: center; text-decoration: none; }
  .workflow-civitai-link:hover, .workflow-civitai-link:focus-visible { background: rgba(255,255,255,.08); }
  .workflow-model-empty { display: grid; place-items: center; min-height: 78px; padding: 6px; text-align: center; font: 700 7px/1.4 monospace; }
  .workflow-pair { display: grid; grid-template-columns: 1fr 1fr; gap: 7px; margin-top: 8px; }
  .workflow-lora-defaults { margin-top: 9px; padding: 8px; background: rgba(255,255,255,.05); color: #b9ae9f; font: 8px/1.45 monospace; }
  .workflow-lora-rows { display: grid; gap: 7px; margin-top: 8px; }
  .workflow-lora-row { display: grid; grid-template-columns: minmax(0,1fr) 64px 26px; gap: 5px; align-items: center; border: 1px solid rgba(244,237,223,.18); padding: 5px; }
  .workflow-lora-selected { display: grid; grid-template-columns: 42px minmax(0,1fr); gap: 7px; align-items: center; min-width: 0; }
  .workflow-lora-selected img, .workflow-lora-selected .workflow-lora-no-image { width: 42px; height: 42px; object-fit: cover; background: #35342f; }
  .workflow-lora-selected .workflow-lora-no-image { display: grid; place-items: center; color: #8e877b; font: 700 7px monospace; }
  .workflow-lora-selected strong, .workflow-lora-selected small { display: block; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .workflow-lora-selected strong { color: #f4eddf; font: 800 9px/1.25 "Avenir Next",sans-serif; }
  .workflow-lora-selected small { margin-top: 3px; color: #aaa395; font: 7px monospace; }
  .workflow-lora-row button, .workflow-add-lora { border: 1px solid rgba(244,237,223,.38); background: transparent; color: #f4eddf; padding: 8px; font: 800 8px monospace; }
  .workflow-add-lora { width: 100%; margin-top: 7px; }
  .workflow-lora-picker { margin-top: 7px; border: 1px solid rgba(244,237,223,.38); background: #24231f; }
  .workflow-lora-picker[hidden] { display: none; }
  .workflow-lora-picker-head { display: flex; justify-content: space-between; gap: 8px; align-items: center; border-bottom: 1px solid rgba(244,237,223,.2); padding: 8px; }
  .workflow-lora-picker-head strong, .workflow-lora-picker-head span { display: block; }
  .workflow-lora-picker-head strong { color: #f4eddf; font: 800 9px monospace; }
  .workflow-lora-picker-head span { margin-top: 2px; color: #aaa395; font: 7px monospace; }
  .workflow-lora-picker-head button { border: 1px solid rgba(244,237,223,.38); background: transparent; color: #f4eddf; padding: 4px 7px; font: 900 13px monospace; }
  .workflow-lora-filter { display: grid; grid-template-columns: minmax(0,1fr) 110px; gap: 5px; padding: 7px; }
  .workflow-lora-filter input, .workflow-lora-filter select { min-width: 0; width: 100%; margin: 0; border: 1px solid rgba(244,237,223,.3); background: #302f2b; color: #f4eddf; padding: 8px; font: 8px monospace; }
  .workflow-lora-picker > p { margin: 0 !important; border-top: 1px solid rgba(244,237,223,.12); padding: 6px 8px; }
  .workflow-lora-results { display: grid; max-height: 270px; overflow-y: auto; overscroll-behavior: contain; border-top: 1px solid rgba(244,237,223,.16); }
  .workflow-lora-result { display: grid; grid-template-columns: 48px minmax(0,1fr) auto; gap: 8px; align-items: center; min-width: 0; border-bottom: 1px solid rgba(244,237,223,.12); padding: 6px; color: #f4eddf; text-align: left; }
  .workflow-lora-result:hover, .workflow-lora-result:focus-visible { background: rgba(255,255,255,.07); }
  .workflow-lora-result img, .workflow-lora-result .workflow-lora-no-image { width: 48px; height: 48px; object-fit: cover; background: #35342f; }
  .workflow-lora-result .workflow-lora-no-image { display: grid; place-items: center; color: #8e877b; font: 700 7px monospace; }
  .workflow-lora-result strong, .workflow-lora-result small { display: block; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .workflow-lora-result strong { font: 800 9px/1.3 "Avenir Next",sans-serif; }
  .workflow-lora-result small { margin-top: 3px; color: #aaa395; font: 7px monospace; }
  .workflow-lora-result > span:last-child { color: var(--acid); font: 900 8px monospace; }
  .workflow-lora-result .workflow-civitai-link { display: inline-block; margin-top: 4px; border-top: 0; border-bottom: 1px solid currentColor; padding: 0; text-align: left; }
  .workflow-lora-add { border: 1px solid rgba(244,237,223,.38); background: transparent; color: var(--acid); padding: 7px; font: 900 8px monospace; }
  .workflow-task-link { margin-top: 8px; border: 0; border-bottom: 1px solid currentColor; background: transparent; color: var(--acid); font: 800 8px monospace; cursor: pointer; }
  .output-actions { display: grid; gap: 8px; margin-top: 22px; }
  .output-actions .creative-action { color: #f4eddf; }
  .output-actions .creative-action.primary { background: var(--acid); color: var(--ink); border-color: var(--acid); }
  .save-state { margin-top: 10px; color: #b9ae9f; font: 9px monospace; text-transform: uppercase; }
  .assist-proposal { margin-top: 12px; padding: 10px; border: 1px solid var(--signal); background: #f4ecdc; }
  .assist-proposal pre { max-height: 180px; overflow: auto; white-space: pre-wrap; font: 10px/1.5 monospace; }
  .assist-proposal-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
  .project-journey { margin: 16px 0 20px; border: 1px solid var(--ink); background: #e9e2d4; }
  .project-journey-head { display: flex; align-items: end; justify-content: space-between; gap: 18px; padding: 15px 16px; border-bottom: 1px solid var(--ink); }
  .project-journey-head h2 { margin: 4px 0 0; font: 700 24px/1 "Iowan Old Style", serif; }
  .project-journey-head button { border-bottom: 1px solid currentColor; color: var(--signal); font: 800 8px monospace; }
  .project-journey-grid { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 1px; background: var(--line); }
  .project-journey-card { position: relative; display: grid; min-width: 0; min-height: 168px; align-content: space-between; gap: 12px; padding: 13px 12px; background: #f2ebde; }
  .project-journey-card::before { content: ""; position: absolute; inset: 0 0 auto; height: 4px; background: #aaa397; }
  .project-journey-card.ready::before { background: #52735d; }
  .project-journey-card strong, .project-journey-card span, .project-journey-card small { display: block; }
  .project-journey-card .journey-number { color: var(--signal); font: 900 9px monospace; }
  .project-journey-card strong { margin-top: 14px; font: 800 11px/1.25 monospace; }
  .project-journey-card .journey-count { margin-top: 7px; font: 700 24px/1 "Iowan Old Style", serif; }
  .project-journey-card small { margin-top: 4px; overflow-wrap: anywhere; color: var(--muted); font: 8px/1.45 monospace; }
  .project-journey-card button { width: 100%; border: 1px solid var(--ink); padding: 7px; text-align: left; font: 800 8px/1.25 monospace; }
  .project-journey-card.ready button { background: var(--ink); color: var(--paper); }
  .project-journey-empty { grid-column: 1/-1; margin: 0; padding: 20px; background: #f2ebde; color: var(--muted); font: 9px monospace; }
  .project-journey-note { margin: 0; padding: 9px 16px; border-top: 1px solid var(--line); color: var(--muted); font: 8px/1.5 monospace; }
  #creativeBrief, #creativeResultsSection, .workflow-dispatch, .output-rail { scroll-margin-top: 96px; }
  .archive-add-tools { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 6px; margin-top: 12px; }
  .archive-add-tools select { min-width: 0; border: 1px solid var(--line); background: #f5f0e4; padding: 8px; font: 10px monospace; }
  .archive-add-button, .character-create-button { background: var(--signal); color: white; padding: 8px 10px; font: 800 9px monospace; }
  .character-actions { display: flex; flex-wrap: wrap; gap: 7px; }
  .recipe-name { width: 100%; margin-top: 12px; border: 1px solid rgba(244,237,223,.35); background: rgba(255,255,255,.06); color: #f4eddf; padding: 9px; }
  @media (max-width: 1180px) { .creative-layout { grid-template-columns: 220px minmax(0, 1fr); } .output-rail { grid-column: 1 / -1; border-left: 0; border-top: 1px solid var(--line); } .project-journey-grid { grid-template-columns: repeat(2,minmax(0,1fr)); } }
  @media (max-width: 760px) { .creative-heading { display: block; background: #ece5d5; } .creative-heading p { margin-top: 12px; } .creative-layout { display: block; } .project-rail { border-right: 0; border-bottom: 1px solid var(--line); } .slot-grid, .project-head, .result-review-tools, .review-slot-grid, .review-findings, .review-actions, .iteration-change, .iteration-panel-actions, .dataset-export-panel, .wd14-toolbar { grid-template-columns: 1fr; } .slot-card:first-child { grid-column: auto; } .reference-list, .sourcing-candidates, .result-gallery, .project-journey-grid { grid-template-columns: 1fr; } .project-journey-card { min-height: 0; } .project-journey-head { align-items: start; } .generation-grid { grid-template-columns: 1fr 1fr; } .workflow-pair { grid-template-columns: 1fr; } .workflow-lora-filter { grid-template-columns: 1fr; } #creativeBrief, #creativeResultsSection, .workflow-dispatch, .output-rail { scroll-margin-top: 176px; } }
</style>
"""

CREATIVE_SCRIPT = r"""
<script>
(() => {
  const slotsMeta = {
    character: ['角色', '人物身份、外观、发色、瞳色与稳定特征'], outfit: ['服装', '衣物、材质、配饰与穿着方式'],
    action: ['动作', '姿态、手部动作、表情与互动'], composition: ['构图', '景别、机位、视角与主体位置'],
    scene: ['场景', '地点、环境物件、天气与时间'], lighting: ['灯光', '光向、色温、明暗与氛围'], style: ['画风', '媒介、审美、质感、LoRA 与风格词']
  };
  const safetyLabels = {sfw:'普通',suggestive:'轻度成人向',adult:'成人向','explicit-adult':'明确成人向',unrated:'尚未分级'};
  const wd14RatingLabels = {general:'普通',sensitive:'轻度成人向',questionable:'成人向',explicit:'明确成人向',unknown:'尚未判断'};
  const creativeState = {project: null, projects: [], recipes: [], outputs: {}, profile: 'anima', workflowProfiles: [], windowsModels: [], windowsLoras: [], modelConnections: [], discoveredModels: [], editingModelConnectionId: '', workflowLoraPickerOpen: false, workflowLoraQuery: '', workflowLoraFolder: '', workflowMessage: '', workflowMessageProjectId: '', datasetProfile: 'anima', datasetMessage: '', datasetMessageProjectId: '', journey: null, journeyProjectId: '', journeyRun: 0, suggestion: null, sourcing: null, sourcingProjectId: '', sourcingRun: 0, review: null, reviewAssetId: '', reviewProjectId: '', iteration: null, iterationProjectId: '', iterationRun: 0, iterationMessage: '', iterationMessageProjectId: '', visionAvailable: false, saveTimer: null, compileTimer: null, loadedMeta: false};

  async function creativeJson(url, options = {}) {
    const response = await fetch(url, options);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || `Request failed: ${response.status}`);
    return data;
  }

  function slotTemplate() {
    return Object.entries(slotsMeta).map(([key, meta]) => `<div class="slot-card" data-slot-card="${key}"><div class="slot-head"><div><label>${meta[0]}</label><small>${meta[1]}</small></div><button class="slot-lock" data-lock-slot="${key}" aria-pressed="false">可以编辑</button></div><textarea data-slot-input="${key}" placeholder="填写 ${meta[0]} 内容…"></textarea></div>`).join('');
  }

  function blankProject() {
    return {title:'未命名绘图项目', brief_zh:'', safety_mode:'sfw', target_profile:'anima', character_id:'', slots:Object.fromEntries(Object.keys(slotsMeta).map(k => [k, ''])), slot_locks:Object.fromEntries(Object.keys(slotsMeta).map(k => [k, false])), references:[], generation:{}, lineage:{}, test_notes:''};
  }

  function iterationOf(project) { const value = Number(project?.lineage?.iteration); return Number.isInteger(value) && value > 0 ? value : 1; }

  function renderProjectJourney() {
    const journey=creativeState.journeyProjectId===creativeState.project?.project_id?creativeState.journey:null, grid=$('#projectJourneyGrid');
    if(!journey) { grid.innerHTML='<p class="project-journey-empty">正在汇总这个项目的进度……</p>'; return; }
    grid.innerHTML=(journey.stages||[]).map((stage,index)=>`<article class="project-journey-card ${stage.state==='ready'?'ready':'pending'}"><div><span class="journey-number">0${index+1} · ${stage.state==='ready'?'已有进展':'等待继续'}</span><strong>${escapeHtml(stage.label)}</strong><span class="journey-count">${Number(stage.count)||0}</span><small>${escapeHtml(stage.detail||stage.status)}</small><small>${escapeHtml(stage.status)}</small></div><button type="button" data-journey-action="${escapeHtml(stage.stage_id)}" data-journey-view="${escapeHtml(stage.action?.view||'creative')}" data-journey-target="${escapeHtml(stage.action?.target_id||'')}">${escapeHtml(stage.action?.label||'继续')}</button></article>`).join('');
    $('#projectJourneyNote').textContent=`已汇总 ${journey.summary?.result_count||0} 张结果、${journey.summary?.selected_count||0} 张精选、${journey.summary?.workspace_count||0} 个关联工作区、${journey.summary?.delivery_count||0} 个交付版本。这里只读状态，不会自动审核。`;
  }

  async function refreshProjectJourney() {
    const projectId=creativeState.project?.project_id, runId=++creativeState.journeyRun; if(!projectId) return;
    const journey=await creativeJson(`/api/creative/projects/${encodeURIComponent(projectId)}/journey`);
    if(runId!==creativeState.journeyRun||creativeState.project?.project_id!==projectId) return;
    creativeState.journey=journey; creativeState.journeyProjectId=projectId; renderProjectJourney();
  }

  async function syncProjectDataset() {
    if(!creativeState.project?.project_id) return;
    await saveCreative(); $('#projectJourneyNote').textContent='正在复制已手动精选的图片并建立来源档案；不会改变审核状态……';
    const result=await creativeJson(`/api/creative/projects/${encodeURIComponent(creativeState.project.project_id)}/dataset-workspace`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({profile_id:creativeState.datasetProfile})});
    await refreshProjectJourney();
    $('#projectJourneyNote').textContent=`已新增 ${result.synced} 张、复用 ${result.existing} 张；扫描在后台进行，图片仍是未审核状态。`;
    await window.setPromptHubView?.('datasets');
    await window.openDatasetWorkspace?.(result.workspace.workspace_id,2);
  }

  async function openCreativeProject(projectId) {
    await ensureCreativeProject();
    if(creativeState.project?.project_id!==projectId) {
      clearTimeout(creativeState.saveTimer); await saveCreative();
      creativeState.project=creativeState.projects.find(item=>item.project_id===projectId)||await creativeJson(`/api/creative/projects/${encodeURIComponent(projectId)}`);
      creativeState.review=null; creativeState.reviewProjectId=''; renderCreativeProject();
    }
    await window.setPromptHubView?.('creative');
  }
  window.openCreativeProject=openCreativeProject;

  function collectCreative() {
    if (!creativeState.project) return blankProject();
    const generation = {...(creativeState.project.generation || {}),
      width: Number($('#genWidth').value) || null, height: Number($('#genHeight').value) || null, steps: Number($('#genSteps').value) || null, cfg: Number($('#genCfg').value) || null, seed: $('#genSeed').value.trim(),
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
    $('#genWidth').value = project.generation?.width ?? '';
    $('#genHeight').value = project.generation?.height ?? '';
    $('#genSteps').value = project.generation?.steps ?? '';
    $('#genCfg').value = project.generation?.cfg ?? '';
    $('#genSeed').value = project.generation?.seed ?? '';
    $('#genResults').value = (project.generation?.result_images || []).join('\n');
    Object.keys(slotsMeta).forEach(key => {
      const input = document.querySelector(`[data-slot-input="${key}"]`); const card = document.querySelector(`[data-slot-card="${key}"]`); const lock = document.querySelector(`[data-lock-slot="${key}"]`);
      input.value = project.slots?.[key] || ''; const locked = Boolean(project.slot_locks?.[key]); card.classList.toggle('is-locked', locked); lock.setAttribute('aria-pressed', String(locked)); lock.textContent = locked ? '已锁定' : '可以编辑';
    });
    creativeState.profile = project.target_profile || creativeState.profile;
    document.querySelectorAll('[data-profile]').forEach(button => button.classList.toggle('active', button.dataset.profile === creativeState.profile));
    renderCreativeReferences(); renderCreativeProjects(); renderLineageNotice(); renderIterationPanel(); renderSourcing(); renderResultGallery(); renderReviewProposal(); renderWorkflowProfiles(); renderProjectJourney(); $('#creativeSaveState').textContent = `项目已加载 · 第 ${iterationOf(project)} 版 · 修订 ${project.revision || 1}`; compileCreative().catch(showCreativeError); loadIterationContext().catch(showCreativeError); refreshProjectJourney().catch(showCreativeError);
  }

  function renderCreativeProjects() {
    $('#creativeProjectList').innerHTML = creativeState.projects.length ? creativeState.projects.map(project => { const iteration = iterationOf(project); const parent = Number(project.lineage?.parent_iteration); const origin = parent > 0 ? ` · 来自第 ${parent} 版` : ''; return `<button class="project-item ${creativeState.project?.project_id === project.project_id ? 'active' : ''}" data-project-id="${escapeHtml(project.project_id)}"><strong>${escapeHtml(project.title)}</strong><span>第 ${iteration} 版 · 修订 ${project.revision}${origin}<br>${escapeHtml((project.updated_at || '').slice(0,16).replace('T',' '))}</span></button>`; }).join('') : '<p class="lm-status">还没有项目。</p>';
  }

  function renderLineageNotice() {
    const notice = $('#lineageNotice'); const project = creativeState.project; const lineage = project?.lineage || {}; const iteration = iterationOf(project);
    if (iteration <= 1 || !lineage.parent_project_id) { notice.hidden = true; notice.textContent = ''; return; }
    const source = lineage.source_asset_filename || '上一轮结果图'; const parent = Number(lineage.parent_iteration) || iteration - 1;
    const sourceUrl = lineage.source_asset_id ? `/result-media/${encodeURIComponent(lineage.parent_project_id)}/original/${encodeURIComponent(lineage.source_asset_id)}` : '';
    notice.hidden = false; notice.innerHTML = `<strong>第 ${iteration} 版</strong> · 基于第 ${parent} 版的 ${escapeHtml(source)} 创建。旧项目和旧结果图保持不变。${sourceUrl ? `<a href="${sourceUrl}" target="_blank" rel="noreferrer">查看来源图</a>` : ''}`;
  }

  function renderIterationPanel() {
    const panel = $('#iterationPanel'); const project = creativeState.project; const iteration = iterationOf(project);
    if (iteration <= 1 || !project?.lineage?.parent_project_id) { panel.hidden = true; return; }
    panel.hidden = false; $('#iterationVersion').textContent = `第 ${Number(project.lineage.parent_iteration) || iteration - 1} 版 → 第 ${iteration} 版`;
    const context = creativeState.iterationProjectId === project.project_id ? creativeState.iteration : null;
    if (!context) { $('#iterationSummary').textContent = '正在读取上一版与图片分析建议…'; $('#iterationSuggestions').innerHTML = ''; $('#iterationChanges').innerHTML = ''; $('#iterationStatus').textContent = '正在建立版本对照…'; $('#applyIterationSuggestions').disabled = true; $('#applyIterationSuggestions').textContent = '暂无可应用建议'; return; }
    const review = context.review || {}; $('#iterationSummary').textContent = review.summary_zh || '这一轮没有保存图片分析摘要。';
    $('#iterationSuggestions').innerHTML = (review.improvements || []).map(item => `<li>${escapeHtml(item)}</li>`).join('') || '<li>这一轮没有结构化改进建议。</li>';
    const visibleChanges = (context.changes || []).filter(item => item.status !== 'unchanged' || (item.suggested && item.suggested !== item.current));
    const statusLabels = {changed:'已修改',added:'本轮新增',removed:'本轮留空',unchanged:'尚未修改',unknown:'上一版不可用'};
    $('#iterationChanges').innerHTML = visibleChanges.length ? visibleChanges.map(item => { const meta = slotsMeta[item.slot] || [item.slot]; const state = item.locked ? ' · 已锁定' : item.applicable ? ' · 可填入建议' : ''; return `<article class="iteration-change"><strong>${escapeHtml(meta[0])}<br>${escapeHtml(statusLabels[item.status] || item.status)}${state}</strong><div><label>上一版</label><p>${escapeHtml(item.previous || '—')}</p></div><div><label>当前版</label><p>${escapeHtml(item.current || '—')}</p></div><div class="suggested"><label>图片分析建议</label><p>${escapeHtml(item.suggested || '—')}</p></div></article>`; }).join('') : '<p class="reference-empty" style="background:#f6f0e4;margin:0;padding:14px 16px">当前内容与上一版一致，也没有新的修改建议。</p>';
    const count = (context.applicable_slots || []).length; const button = $('#applyIterationSuggestions'); button.disabled = count === 0; button.textContent = count ? `确认填入 ${count} 个空槽位` : '没有可直接填入的建议';
    const savedMessage = creativeState.iterationMessageProjectId === project.project_id ? creativeState.iterationMessage : '';
    $('#iterationStatus').textContent = savedMessage || (context.parent_available ? '只会填入空白且未锁定的部分，已有内容不会被替换。' : '上一版项目不可用；仍可查看已经保存的图片分析建议。');
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
    $('#creativeReferences').innerHTML = refs.length ? refs.map((ref, index) => { const visual = ref.visuals?.[0],type=slotsMeta[ref.slot]?.[0]||'参考资料'; return `<article class="reference-card">${visual ? `<img src="${escapeHtml(visual.thumbnail_url)}" alt="${escapeHtml(ref.title)}">` : ''}<div><button class="reference-remove" data-remove-reference="${index}">移除</button><strong>${escapeHtml(ref.title || '未命名参考')}</strong><span>${escapeHtml(type)}</span></div></article>`; }).join('') : '<p class="reference-empty">还没有参考资料。去“提示词库”找到卡片后，选择槽位并点击“加入创作”。</p>';
  }

  function renderResultGallery() {
    const assets = creativeState.project?.generation?.result_assets || [];
    const profileLabel = creativeState.datasetProfile === 'anima' ? 'Anima 英文标签' : 'Krea 2 英文自然语言';
    $('#datasetProfile').value = creativeState.datasetProfile;
    $('#resultGallery').innerHTML = assets.length ? assets.map(asset => renderResultCard(asset, profileLabel)).join('') : '<p class="reference-empty">还没有导入结果图。你可以从 Windows、共享目录或下载文件中选择 PNG、JPEG、WebP。</p>';
    const selectedCount = assets.filter(asset => asset.dataset_selected === true).length;
    $('#exportDataset').disabled = selectedCount === 0;
    $('#tagSelectedDataset').disabled = selectedCount === 0 || selectedCount > 24;
    const savedMessage = creativeState.datasetMessageProjectId === creativeState.project?.project_id ? creativeState.datasetMessage : '';
    $('#datasetExportStatus').textContent = savedMessage || (selectedCount > 24 ? `已精选 ${selectedCount} 张；同步 WD14 每次最多 24 张，导出不受影响。` : selectedCount ? `已精选 ${selectedCount} 张；将按 ${profileLabel} 生成同名说明文件。` : '先在上方手动精选结果图；导出不会改动原图。');
    const localeTags = assets.flatMap(asset => { const tagging = asset.wd14_tagging || {}; return [...(tagging.general || []).map(item => item.tag), ...(tagging.characters || []).map(item => item.tag), ...String(tagging.draft_tags || '').split(',')]; }).filter(Boolean);
    if (window.ensureTagLabels && localeTags.length) window.ensureTagLabels(localeTags).then(changed => { if (changed) renderResultGallery(); }).catch(console.error);
  }

  function renderResultCard(asset, profileLabel) {
    const selected = asset.dataset_selected === true; const captions = asset.dataset_captions || {}; const caption = captions[creativeState.datasetProfile] || '';
    return `<article class="result-card ${selected ? 'is-dataset-selected' : ''}"><a href="${escapeHtml(asset.original_url)}" target="_blank" rel="noreferrer"><img src="${escapeHtml(asset.thumbnail_url)}" alt="${escapeHtml(asset.filename || '本地结果图')}" loading="lazy"></a><div class="result-card-body"><strong>${escapeHtml(asset.filename || '本地结果图')}</strong><span>${Number(asset.width) || '?'} × ${Number(asset.height) || '?'} · ${escapeHtml(safetyLabels[asset.safety] || '尚未分级')}</span><button class="dataset-toggle ${selected ? 'is-selected' : ''}" data-dataset-toggle="${escapeHtml(asset.asset_id)}">${selected ? '✓ 已加入数据集' : '＋ 加入数据集'}</button><button class="wd14-run" data-wd14-tag="${escapeHtml(asset.asset_id)}">${asset.wd14_tagging ? '重新运行 WD14' : '用 WD14 生成标签'}</button>${renderWd14Review(asset)}<details class="dataset-caption"><summary>${profileLabel}说明 · 留空时使用项目输出</summary><textarea data-dataset-caption="${escapeHtml(asset.asset_id)}" maxlength="12000" placeholder="留空时采用当前项目的 ${profileLabel}正向提示词">${escapeHtml(caption)}</textarea><button data-save-caption="${escapeHtml(asset.asset_id)}">保存此图说明</button></details><button data-review-asset="${escapeHtml(asset.asset_id)}" ${creativeState.visionAvailable ? '' : 'disabled'}>${creativeState.visionAvailable ? '用所选模型分析图片' : '暂无视觉模型'}</button></div></article>`;
  }

  function renderWd14Review(asset) {
    const tagging = asset.wd14_tagging; if (!tagging) return '';
    const rating = tagging.rating?.tag || 'unknown'; const ratingScore = Number(tagging.rating?.score); const characters = (tagging.characters || []).map(item => item.tag).filter(Boolean);
    const draft = tagging.draft_tags || ''; const draftValues = draft.split(',').map(value => value.trim()).filter(Boolean); const selectedTags = new Set(draftValues.map(value => value.toLowerCase())); const candidates = [...new Set([...(tagging.general || []).map(item => item.tag).filter(Boolean), ...draftValues])]; const animaCaption = asset.dataset_captions?.anima || ''; const confirmed = Boolean(tagging.confirmed_at) && animaCaption === draft;
    const state = confirmed ? '已用作 Anima 标签' : tagging.confirmed_at ? 'Anima 标签后来又有修改' : '尚未确认';
    const chips = candidates.map(tag => `<button class="wd14-tag-chip ${selectedTags.has(tag.toLowerCase()) ? 'selected' : ''}" data-wd14-chip="${escapeHtml(asset.asset_id)}" data-tag-value="${escapeHtml(tag)}" aria-pressed="${selectedTags.has(tag.toLowerCase())}">${escapeHtml(window.displayCanonicalTag ? window.displayCanonicalTag(tag) : tag)}</button>`).join('');
    const language = window.getTagDisplayLanguage?.() === 'en' ? '只看英文标签' : '查看中英标签';
    const characterLabels = characters.map(tag => window.displayCanonicalTag ? window.displayCanonicalTag(tag) : tag);
    return `<details class="wd14-review" open><summary>WD14 草稿 · ${escapeHtml(wd14RatingLabels[rating] || rating)} ${Number.isFinite(ratingScore) ? Math.round(ratingScore * 100) + '%' : ''} · ${state}</summary><p>角色候选：${escapeHtml(characterLabels.join(', ') || '无（原创 OC 常见）')}<br>普通标签最低可信度 ${Number(tagging.general_threshold).toFixed(2)} · 角色标签最低可信度 ${Number(tagging.character_threshold).toFixed(2)} · 运行方式 ${escapeHtml(tagging.provider || 'CPU')}</p><div class="wd14-tag-locale"><span>点击标签保留或移除；保存和导出始终使用英文标签。</span><button data-toggle-tag-language>${language}</button></div><div class="wd14-tag-chips">${chips}</div><details class="wd14-advanced"><summary>直接编辑英文标签</summary><textarea data-wd14-draft="${escapeHtml(asset.asset_id)}" maxlength="12000" aria-label="WD14 Anima 标签草稿">${escapeHtml(draft)}</textarea></details><div class="wd14-actions"><button data-save-wd14="${escapeHtml(asset.asset_id)}">保存审核草稿</button><button data-confirm-wd14="${escapeHtml(asset.asset_id)}">确认用作 Anima 标签</button></div></details>`;
  }

  function toggleWd14Chip(assetId, tag) {
    const asset = (creativeState.project?.generation?.result_assets || []).find(item => item.asset_id === assetId); if (!asset?.wd14_tagging) return;
    const values = String(asset.wd14_tagging.draft_tags || '').split(',').map(value => value.trim()).filter(Boolean); const key = tag.toLowerCase(); const exists = values.some(value => value.toLowerCase() === key); asset.wd14_tagging.draft_tags = (exists ? values.filter(value => value.toLowerCase() !== key) : [...values, tag]).join(', '); renderResultGallery();
  }

  function updateVisionHint() {
    const select = $('#visionModel'); const option = select.options[select.selectedIndex];
    if (!creativeState.visionAvailable || !option) { $('#resultModelHint').textContent = '暂无可用视觉模型。可以在 LM Studio 加载视觉模型，或连接支持看图的外部模型。'; return; }
    if (option.dataset.source === 'external') { $('#resultModelHint').textContent = '当前选择外部视觉模型；图片会发送到该 API 服务。'; return; }
    const loaded = option.textContent.trim().startsWith('●');
    $('#resultModelHint').textContent = loaded
      ? '● 当前视觉模型已加载，可以直接分析图片。'
      : '○ 当前模型尚未加载。24GB Mac 请先在 LM Studio 卸载文字模型，再只加载这一只视觉模型。';
  }

  function renderReviewProposal() {
    const proposal = $('#reviewProposal'); const review = creativeState.review;
    if (!review || creativeState.reviewProjectId !== creativeState.project?.project_id) { proposal.hidden = true; return; }
    proposal.hidden = false; $('#reviewModelName').textContent = review.model || '视觉模型'; $('#reviewSummary').textContent = review.summary_zh || '模型没有提供摘要。';
    const current = collectCreative();
    $('#reviewSlots').innerHTML = Object.entries(slotsMeta).map(([slot, meta]) => { const value = review.observed_slots?.[slot] || ''; const state = current.slot_locks?.[slot] ? '已锁定，不写回' : current.slots?.[slot] ? '已有内容，仅展示' : '空槽位，可确认补充'; return `<article class="review-slot"><strong>${meta[0]}</strong><p>${escapeHtml(value || '未识别到明确内容')}</p><span>${state}</span></article>`; }).join('');
    const findingMeta = [['strengths','优点'],['issues','问题'],['improvements','下一轮建议']];
    $('#reviewFindings').innerHTML = findingMeta.map(([key,label]) => `<section class="review-finding"><strong>${label}</strong><ul>${(review[key] || []).map(item => `<li>${escapeHtml(item)}</li>`).join('') || '<li>无</li>'}</ul></section>`).join('');
    const prompts = review.reconstructed_prompts || {};
    $('#reviewPrompts').textContent = `Anima 正向提示词\n${prompts.anima_positive || ''}\n\nAnima 负面提示词\n${prompts.anima_negative || ''}\n\nKrea 2 正向提示词\n${prompts.krea2_positive || ''}\n\nKrea 2 排除内容\n${prompts.krea2_avoid || ''}`;
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
        return `<article class="sourcing-card ${visual ? '' : 'no-image'}">${visual ? `<img src="${escapeHtml(visual.thumbnail_url)}" alt="${escapeHtml(item.title || meta[0])}">` : ''}<div class="sourcing-card-body"><strong class="sourcing-card-title">${escapeHtml(item.title || item.content || '未命名资料')}</strong><p class="sourcing-card-content">${escapeHtml(item.content || item.title || '')}</p><span class="sourcing-card-meta">${escapeHtml(item.match_reason || item.kind || '')}<br>命中：${escapeHtml(item.match_query || '')} · ${escapeHtml(safetyLabels[item.safety] || '尚未分级')}</span><button class="sourcing-add ${added ? 'is-added' : ''}" data-source-slot="${slot}" data-source-index="${index}">${added ? '✓ 已加入，可再次查看' : `＋ 加入${meta[0]}槽位`}</button></div></article>`;
      }).join('');
      const empty = group.locked ? '此槽位已锁定，本轮不检索。' : (group.queries || []).length ? '本轮没有找到足够相关的本地资料。' : '没有识别出这个槽位的检索词；可先手动补充槽位内容。';
      return `<section class="sourcing-group"><div class="sourcing-group-head"><strong>${meta[0]}</strong><span>${group.locked ? '已锁定，不会加入' : `${(group.candidates || []).length} 条可选参考`}</span></div>${queries ? `<div class="sourcing-queries">${queries}</div>` : ''}${candidates ? `<div class="sourcing-candidates">${candidates}</div>` : `<p class="sourcing-empty">${empty}</p>`}</section>`;
    }).join('');
    $('#sourcingGroups').innerHTML = groups;
  }

  function renderCreativeRecipes() {
    $('#creativeRecipeList').innerHTML = creativeState.recipes.length ? creativeState.recipes.map(recipe => { const safety=recipe.snapshot?.project?.safety_mode; return `<button class="recipe-item" data-recipe-id="${escapeHtml(recipe.recipe_id)}"><strong>${escapeHtml(recipe.name)}</strong><span>${escapeHtml((recipe.updated_at || '').slice(0,10))} · ${escapeHtml(safetyLabels[safety] || '尚未分级')}</span></button>`; }).join('') : '<p class="lm-status">还没有保存配方。</p>';
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

  const workflowAssetLabels = {diffusion_model:'扩散模型（Diffusion Model）',vae:'VAE',text_encoder:'文本编码器'};

  function selectedWorkflowProfile() { const profiles=matchingWorkflowProfiles(); return profiles.find(profile=>profile.profile_id===$('#workflowProfile').value)||profiles[0]; }

  function storedWorkflowControls(profileId) { const all=creativeState.project?.generation?.workflow_controls; const value=all&&typeof all==='object'?all[profileId]:null; return value&&typeof value==='object'?value:{models:{},loras:[],sampler:'',scheduler:''}; }

  function workflowCompatibleModels(profile, control) { return creativeState.windowsModels.filter(item=>item.asset_type===control.asset_type&&['', 'unknown', profile.model_family].includes(String(item.model_family||'').toLowerCase())); }

  function workflowModelOptions(profile, control, selectedId) { const compatible=workflowCompatibleModels(profile,control),fallback=`使用工作流原设置 · ${control.current||'未记录'}`; return `<option value="">${escapeHtml(fallback)}</option>`+compatible.map(item=>`<option value="${escapeHtml(item.asset_id)}" ${item.asset_id===selectedId?'selected':''}>${escapeHtml(item.name)} · ${escapeHtml(item.relative_path)}</option>`).join(''); }

  function workflowSelectedModel(profile, control, selectedId) { const compatible=workflowCompatibleModels(profile,control); if(selectedId) return compatible.find(item=>item.asset_id===selectedId)||null; const current=String(control.current||'').replaceAll('\\','/').toLowerCase(); return compatible.find(item=>String(item.relative_path||'').toLowerCase()===current)||null; }

  function workflowCivitaiLink(item,label='Civitai / 提示词 ↗') { return item?.source_url?`<a class="workflow-civitai-link" href="${escapeHtml(item.source_url)}" target="_blank" rel="noreferrer">${escapeHtml(label)}</a>`:''; }

  function workflowModelVisual(item) { if(!item) return '<div class="workflow-model-visual workflow-model-empty">默认底模尚未匹配清单</div>'; const previews=item.preview_urls||[],preview=previews.length?`<a class="workflow-model-preview" href="${escapeHtml(previews[0])}" target="_blank" rel="noreferrer" title="打开底模示例图"><img src="${escapeHtml(previews[0])}" alt="${escapeHtml(item.name)} 底模示例图" loading="lazy"><span>${previews.length} 张</span></a>`:'<div class="workflow-model-empty">尚无同名示例图</div>'; return `<div class="workflow-model-visual">${preview}${workflowCivitaiLink(item)}</div>`; }

  function workflowCompatibleLoras(profile) { return creativeState.windowsLoras.filter(item=>['', 'unknown', profile.model_family].includes(String(item.model_family||'').toLowerCase())); }

  function workflowLoraFolder(item) { const parts=String(item.relative_path||'').split('/').filter(Boolean); return parts.length>1?parts.slice(0,-1).slice(0,2).join('/'):'未分类'; }

  function workflowLoraSearchText(item) { return [item.name,item.relative_path,item.base_model,item.model_family,...(item.trigger_words||[]),...(item.tags||[])].join(' ').toLocaleLowerCase(); }

  function workflowLoraVisual(item, compact=false) { const preview=item?.preview_urls?.[0]; return preview?`<img src="${escapeHtml(preview)}" alt="${escapeHtml(item.name)} LoRA 示例图" loading="lazy">`:`<span class="workflow-lora-no-image">${compact?'L':'无图'}</span>`; }

  function renderWorkflowLoraPicker(profile, selectedIds) { const picker=$('#workflowLoraPicker'),compatible=workflowCompatibleLoras(profile),folders=[...new Set(compatible.map(workflowLoraFolder))].sort((a,b)=>a.localeCompare(b,'zh-CN',{numeric:true,sensitivity:'base'})); if(!folders.includes(creativeState.workflowLoraFolder)) creativeState.workflowLoraFolder=''; $('#workflowLoraFolder').innerHTML=`<option value="">全部文件夹 · ${compatible.length}</option>`+folders.map(folder=>`<option value="${escapeHtml(folder)}" ${folder===creativeState.workflowLoraFolder?'selected':''}>${escapeHtml(folder)}</option>`).join(''); $('#workflowLoraSearch').value=creativeState.workflowLoraQuery; const needle=creativeState.workflowLoraQuery.trim().toLocaleLowerCase(),matched=compatible.filter(item=>!selectedIds.has(item.lora_id)&&(!creativeState.workflowLoraFolder||workflowLoraFolder(item)===creativeState.workflowLoraFolder)&&(!needle||workflowLoraSearchText(item).includes(needle))),visible=matched.slice(0,60); $('#workflowLoraPickerStatus').textContent=matched.length>visible.length?`找到 ${matched.length} 个，当前显示前 ${visible.length} 个；继续输入可缩小范围。`:`找到 ${matched.length} 个可选 LoRA。`; $('#workflowLoraResults').innerHTML=visible.length?visible.map(item=>`<article class="workflow-lora-result">${workflowLoraVisual(item)}<span><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(workflowLoraFolder(item))} · ${escapeHtml(item.relative_path)}</small>${workflowCivitaiLink(item,'查看 Civitai ↗')}</span><button class="workflow-lora-add" type="button" data-workflow-lora-pick="${escapeHtml(item.lora_id)}">添加</button></article>`).join(''):'<div class="workflow-model-empty">当前搜索或文件夹下没有可添加的 LoRA。</div>'; picker.hidden=!creativeState.workflowLoraPickerOpen; }

  function renderWorkflowControls() {
    const profile=selectedWorkflowProfile(),container=$('#workflowControlList');
    if(!profile||!creativeState.project) { container.innerHTML='<p>请先选择一个可用的 ComfyUI 工作流。</p>'; return; }
    const stored=storedWorkflowControls(profile.profile_id),schema=profile.controls||{},models=stored.models||{};
    const modelRows=(schema.model_inputs||[]).map(control=>{ const label=escapeHtml(workflowAssetLabels[control.asset_type]||control.asset_type),select=`<label>${label}<select data-workflow-model="${escapeHtml(control.asset_type)}">${workflowModelOptions(profile,control,models[control.asset_type]||'')}</select></label>`; if(!['checkpoint','diffusion_model'].includes(control.asset_type)) return select; return `<div class="workflow-model-card">${select}${workflowModelVisual(workflowSelectedModel(profile,control,models[control.asset_type]||''))}</div>`; }).join('');
    container.innerHTML=modelRows||'<p>这个工作流没有可在这里切换的模型。</p>';
    const defaults=(schema.default_loras||[]).map(item=>`${item.name} @ ${Number(item.strength).toFixed(2)}`).join('、');
    $('#workflowDefaultLoras').textContent=defaults?`工作流会保留这些默认 LoRA：${defaults}`:'这个工作流没有启用默认 LoRA。';
    $('#workflowSampler').innerHTML=`<option value="">默认 · ${escapeHtml(schema.current_sampler||'未记录')}</option>`+(schema.samplers||[]).map(value=>`<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join('');
    $('#workflowScheduler').innerHTML=`<option value="">默认 · ${escapeHtml(schema.current_scheduler||'未记录')}</option>`+(schema.schedulers||[]).map(value=>`<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join('');
    $('#workflowSampler').value=stored.sampler||''; $('#workflowScheduler').value=stored.scheduler||'';
    const rows=Array.isArray(stored.loras)?stored.loras:[],selectedIds=new Set(rows.map(item=>item.lora_id));
    $('#workflowLoraRows').innerHTML=rows.map((item,index)=>{ const lora=creativeState.windowsLoras.find(value=>value.lora_id===item.lora_id),name=lora?.name||item.lora_id,path=lora?.relative_path||'清单中已不存在'; return `<div class="workflow-lora-row" data-workflow-lora-row="${index}"><div class="workflow-lora-selected">${workflowLoraVisual(lora,true)}<span><strong>${escapeHtml(name)}</strong><small>${escapeHtml(path)}</small>${workflowCivitaiLink(lora,'查看 Civitai ↗')}<input data-workflow-lora-id type="hidden" value="${escapeHtml(item.lora_id||'')}"></span></div><label>强度<input data-workflow-lora-strength type="number" min="-2" max="2" step="0.05" value="${escapeHtml(item.strength??0.8)}"></label><button type="button" data-workflow-lora-remove="${index}" aria-label="移除 ${escapeHtml(name)}">×</button></div>`; }).join('');
    $('#workflowAddLora').disabled=rows.length>=Number(schema.max_additional_loras||4)||workflowCompatibleLoras(profile).length===0;
    renderWorkflowLoraPicker(profile,selectedIds);
    $('#workflowControlHint').textContent=creativeState.windowsModels.length?`已读取 ${creativeState.windowsModels.length} 个模型和 ${creativeState.windowsLoras.length} 个 LoRA。可以搜索名称或按 Windows 文件夹筛选。`:'还没有同步 Windows 模型清单；仍可使用工作流原来的模型。';
  }

  function saveWorkflowControlsFromForm() { const profile=selectedWorkflowProfile(); if(!profile||!creativeState.project) return; const models=Object.fromEntries([...document.querySelectorAll('[data-workflow-model]')].map(select=>[select.dataset.workflowModel,select.value]).filter(([,value])=>value)); const loras=[...document.querySelectorAll('[data-workflow-lora-row]')].map(row=>({lora_id:row.querySelector('[data-workflow-lora-id]').value,strength:Number(row.querySelector('[data-workflow-lora-strength]').value)})).filter(item=>item.lora_id); const all={...(creativeState.project.generation?.workflow_controls||{})}; all[profile.profile_id]={models,loras,sampler:$('#workflowSampler').value,scheduler:$('#workflowScheduler').value}; creativeState.project.generation={...(creativeState.project.generation||{}),workflow_controls:all}; queueCreativeSave(); }

  function renderWorkflowProfiles() {
    const select = $('#workflowProfile'); const profiles = matchingWorkflowProfiles(); const previous = select.value;
    select.innerHTML = profiles.map(profile => `<option value="${escapeHtml(profile.profile_id)}">${escapeHtml(profile.label)} · ${profile.node_count} 个节点</option>`).join('');
    if (profiles.some(profile => profile.profile_id === previous)) select.value = previous;
    const selected = profiles.find(profile => profile.profile_id === select.value) || profiles[0];
    $('#sendWorkflow').disabled = !selected || !creativeState.project?.project_id;
    renderWorkflowControls();
    const currentMessage = creativeState.workflowMessageProjectId === creativeState.project?.project_id ? creativeState.workflowMessage : '';
    if (currentMessage) { $('#workflowRunStatus').textContent = currentMessage; return; }
    if (!selected) { $('#workflowRunStatus').textContent = `还没有导入适用于 ${creativeState.profile === 'anima' ? 'Anima' : 'Krea 2'} 的 ComfyUI 工作流。`; return; }
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
    renderCreativeProjects(); $('#creativeSaveState').textContent = `已保存 · R${creativeState.project.revision}`; await Promise.all([loadIterationContext(),refreshProjectJourney()]);
  }

  async function sendWorkflowProfile() {
    if (!creativeState.project?.project_id) throw new Error('请先建立一个创作项目');
    await saveCreative(); await compileCreative();
    const profileId = $('#workflowProfile').value;
    if (!profileId) throw new Error('当前模型类型还没有可用的 ComfyUI 工作流');
    const button = $('#sendWorkflow'); button.disabled = true; button.textContent = '正在投递…';
    creativeState.workflowMessageProjectId = creativeState.project.project_id;
    creativeState.workflowMessage = '正在把生成包保存到 Mac，并发送到 5060 Ti…'; renderWorkflowProfiles();
    try {
      const result = await creativeJson(`/api/workflow-profiles/${encodeURIComponent(profileId)}/tasks`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({project_id:creativeState.project.project_id, low_cost:$('#workflowLowCost').checked})});
      creativeState.workflowMessage = `已发送“${result.profile.label}”。请到“设备连接”的任务状态查看进度和回传图片。`; await refreshProjectJourney();
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

  function renderExternalModelConnections() {
    const candidates = $('#externalModelCandidates');
    candidates.innerHTML = creativeState.discoveredModels.length ? creativeState.discoveredModels.map(model => `<div class="external-model-candidate"><span title="${escapeHtml(model.id)}">${escapeHtml(model.name || model.id)}</span><button type="button" data-use-external-model="${escapeHtml(model.id)}">选择</button></div>`).join('') : '';
    const list = $('#externalModelList');
    list.innerHTML = creativeState.modelConnections.length ? creativeState.modelConnections.map(item => `<div class="external-model-item"><span title="${escapeHtml(item.base_url)} · ${escapeHtml(item.model_name)}">${escapeHtml(item.label)}${item.supports_vision ? ' · 可看图' : ''}${item.has_api_key ? ' · 已保存密钥' : ''}</span><div class="external-model-item-actions"><button type="button" data-edit-external-model="${escapeHtml(item.id)}">编辑</button><button type="button" data-delete-external-model="${escapeHtml(item.id)}">删除</button></div></div>`).join('') : '<p class="external-model-status">还没有保存外部模型。</p>';
  }

  function clearExternalModelForm() {
    creativeState.editingModelConnectionId = '';
    $('#externalModelLabel').value = ''; $('#externalModelBaseUrl').value = ''; $('#externalModelApiKey').value = ''; $('#externalModelName').value = ''; $('#externalModelVision').checked = false;
    $('#saveExternalModel').textContent = '保存这个模型'; $('#cancelExternalModelEdit').hidden = true;
  }

  function editExternalModel(connectionId) {
    const item = creativeState.modelConnections.find(connection => connection.id === connectionId);
    if (!item) return;
    creativeState.editingModelConnectionId = item.id;
    $('#externalModelLabel').value = item.label || ''; $('#externalModelBaseUrl').value = item.base_url || ''; $('#externalModelApiKey').value = ''; $('#externalModelName').value = item.model_name || ''; $('#externalModelVision').checked = Boolean(item.supports_vision);
    $('#saveExternalModel').textContent = '保存修改'; $('#cancelExternalModelEdit').hidden = false; $('#externalModelSettings').open = true;
    $('#externalModelStatus').textContent = '正在编辑已有连接。API Key 留空会保留原密钥。';
  }

  async function discoverExternalModels() {
    const baseUrl = $('#externalModelBaseUrl').value.trim();
    if (!baseUrl) throw new Error('请先填写 Base URL');
    const button = $('#discoverExternalModels'); button.disabled = true; button.textContent = '正在读取…';
    $('#externalModelStatus').textContent = '正在由本机后端读取模型列表，密钥不会返回网页。';
    try {
      const result = await creativeJson('/api/model-connections/discover', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({base_url:baseUrl, api_key:$('#externalModelApiKey').value})});
      creativeState.discoveredModels = result.models || []; renderExternalModelConnections();
      $('#externalModelStatus').textContent = creativeState.discoveredModels.length ? `读取到 ${creativeState.discoveredModels.length} 个模型，请选择一个。` : '服务没有返回模型列表，可以在下方手工填写模型名称。';
    } finally { button.disabled = false; button.textContent = '读取可用模型'; }
  }

  async function saveExternalModel() {
    const baseUrl = $('#externalModelBaseUrl').value.trim(); const modelName = $('#externalModelName').value.trim();
    if (!baseUrl || !modelName) throw new Error('请填写 Base URL 和模型名称');
    const button = $('#saveExternalModel'); button.disabled = true; button.textContent = '正在保存…';
    try {
      const saved = await creativeJson('/api/model-connections', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({connection_id:creativeState.editingModelConnectionId, label:$('#externalModelLabel').value.trim() || modelName, provider:'openai_compatible', base_url:baseUrl, api_key:$('#externalModelApiKey').value, model_name:modelName, supports_vision:$('#externalModelVision').checked})});
      clearExternalModelForm(); $('#externalModelStatus').textContent = `已保存 ${saved.label}。密钥输入框已清空。`;
      await loadCreativeMeta();
    } finally { button.disabled = false; button.textContent = creativeState.editingModelConnectionId ? '保存修改' : '保存这个模型'; }
  }

  async function deleteExternalModel(connectionId) {
    if (!confirm('确定删除这个外部模型连接吗？本地 LM Studio 不受影响。')) return;
    await creativeJson(`/api/model-connections/${encodeURIComponent(connectionId)}`, {method:'DELETE'});
    if (creativeState.editingModelConnectionId === connectionId) clearExternalModelForm();
    $('#externalModelStatus').textContent = '外部模型连接已删除。'; await loadCreativeMeta();
  }

  async function loadCreativeMeta() {
    const modelCatalog = creativeJson('/api/models').catch(() => creativeJson('/api/local-models'));
    const savedConnections = creativeJson('/api/model-connections').catch(error => { $('#externalModelStatus').textContent = `外部模型配置读取失败：${error.message}`; return []; });
    const [projects, recipes, models, workflowProfiles, windowsModels, windowsLoras, connections] = await Promise.all([creativeJson('/api/creative/projects'), creativeJson('/api/creative/recipes'), modelCatalog, creativeJson('/api/workflow-profiles'), creativeJson('/api/windows-models?limit=2000'), creativeJson('/api/windows-loras?limit=500'), savedConnections]);
    creativeState.projects = projects; creativeState.recipes = recipes; renderCreativeProjects(); renderCreativeRecipes();
    creativeState.workflowProfiles = workflowProfiles; creativeState.windowsModels=windowsModels.results||[]; creativeState.windowsLoras=windowsLoras.results||[]; renderWorkflowProfiles();
    creativeState.modelConnections = connections; renderExternalModelConnections();
    const select = $('#lmModel'); select.innerHTML = models.models.map(model => `<option value="${escapeHtml(model.id)}" data-source="${escapeHtml(model.source || 'local')}">${model.loaded ? '● ' : ''}${escapeHtml(model.name || model.id)}${model.params ? ` · ${escapeHtml(model.params)}` : ''}</option>`).join('');
    const loaded = models.models.find(model => model.loaded);
    const quickFallback = models.models.find(model => model.id.includes('qwen3.5-9b'));
    const preferred = loaded || quickFallback || models.models[0];
    if (preferred) select.value = preferred.id; else select.innerHTML = '<option value="">暂无可用模型</option>';
    select.disabled = !preferred;
    const visionModels = models.models.filter(model => model.vision); const visionSelect = $('#visionModel');
    visionSelect.innerHTML = visionModels.map(model => `<option value="${escapeHtml(model.id)}" data-source="${escapeHtml(model.source || 'local')}">${model.loaded ? '● ' : ''}${escapeHtml(model.name || model.id)}${model.params ? ` · ${escapeHtml(model.params)}` : ''}</option>`).join('');
    const loadedVision = visionModels.find(model => model.loaded); const visionFallback = visionModels.find(model => model.id.includes('qwen3.5-9b')); const preferredVision = visionFallback || loadedVision || visionModels[0];
    if (preferredVision) visionSelect.value = preferredVision.id;
    creativeState.visionAvailable = Boolean(models.available && visionModels.length); visionSelect.disabled = !creativeState.visionAvailable;
    updateVisionHint();
    const localCount = Number(models.local_count ?? models.models.filter(model => model.source !== 'external').length); const externalCount = Number(models.external_count ?? models.models.filter(model => model.source === 'external').length);
    $('#lmStatus').textContent = models.available ? `可用模型：LM Studio ${localCount} 个，外部 ${externalCount} 个；默认优先已加载的本地模型。` : '当前没有可用模型，手动编辑与双格式输出仍可使用。';
    $('#assistCreative').disabled = !models.available || !models.models.length;
    creativeState.loadedMeta = true;
  }

  async function ensureCreativeProject() {
    if (!creativeState.loadedMeta) await loadCreativeMeta();
    if (!creativeState.project) creativeState.project = creativeState.projects[0] || await createCreativeProject();
    renderCreativeProject();
  }
  window.ensureCreativeProject = ensureCreativeProject;

  async function addEntryToCreative(item, slot) {
    await ensureCreativeProject();
    const project = collectCreative(); const current = project.slots[slot] || ''; const addition = item.content || item.title || '';
    if (addition && !current.includes(addition)) project.slots[slot] = [current, addition].filter(Boolean).join(', ');
    const key = `${item.source_id}:${item.external_id}:${slot}`;
    if (!project.references.some(ref => ref.key === key)) project.references.push({key, slot, source_id:item.source_id, external_id:item.external_id, title:item.title, kind:item.kind, safety:item.safety, source_url:item.source_url || '', visuals:item.visuals || []});
    creativeState.project = project; renderCreativeProject(); await saveCreative(); await setView('creative');
  }

  function sourcingPayload(queryHints = {}) {
    const project = collectCreative();
    return {brief:project.brief_zh, slots:project.slots, slot_locks:project.slot_locks, safety_mode:project.safety_mode, query_hints:queryHints, limit_per_slot:6};
  }

  function setSourcingStatus(message) {
    $('#sourcingStatus').textContent = message;
    $('#sourcingRailStatus').textContent = message;
  }

  async function expandCreativeSourcing(runId, payload) {
    const model = $('#lmModel').value;
    if (!model || $('#assistCreative').disabled) {
      setSourcingStatus(`本地快速检索完成：${creativeState.sourcing?.candidate_count || 0} 条真实资料。LM Studio 未连接，本轮不做检索词扩展。`);
      return;
    }
    try {
      const expanded = await creativeJson('/api/creative/source/expand', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({brief:payload.brief, slots:payload.slots, slot_locks:payload.slot_locks, model})});
      if (runId !== creativeState.sourcingRun) return;
      setSourcingStatus(`本地结果已可用；${expanded.model || '本地模型'} 已扩展检索词，正在补充候选…`);
      const enriched = await creativeJson('/api/creative/source', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({...payload, query_hints:expanded.queries})});
      if (runId !== creativeState.sourcingRun) return;
      creativeState.sourcing = enriched; renderSourcing();
      setSourcingStatus(`找到 ${enriched.candidate_count} 条本地参考资料。${expanded.model || '本地模型'} 帮您补充了检索词，但没有自动写入画面。`);
    } catch (error) {
      if (runId !== creativeState.sourcingRun) return;
      setSourcingStatus(`本地候选仍可使用；模型扩展未完成：${error.message}`);
    }
  }

  async function runCreativeSourcing() {
    await ensureCreativeProject();
    const payload = sourcingPayload();
    if (!payload.brief) throw new Error('请先写一段中文创作想法');
    const runId = ++creativeState.sourcingRun;
    const button = $('#sourceCreative'); button.disabled = true; button.textContent = '正在检索本地资料…';
    creativeState.sourcingProjectId = creativeState.project.project_id; $('#sourcingPanel').hidden = false; setSourcingStatus('正在按七个槽位检索本机资料库…');
    try {
      const result = await creativeJson('/api/creative/source', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
      if (runId !== creativeState.sourcingRun) return;
      creativeState.sourcing = result; renderSourcing();
      setSourcingStatus(`本地快速检索完成：${result.candidate_count} 条真实资料。正在由已加载模型扩展检索词…`);
      expandCreativeSourcing(runId, payload);
    } finally {
      if (runId === creativeState.sourcingRun) { button.disabled = false; button.textContent = '从提示词库找参考'; }
    }
  }

  async function uploadResultImage() {
    await ensureCreativeProject(); const file = $('#resultImageFile').files?.[0];
    if (!file) throw new Error('请先选择一张 PNG、JPEG 或 WebP 结果图');
    if (file.size > 25 * 1024 * 1024) throw new Error('结果图不能超过 25 MiB');
    await saveCreative(); const button = $('#uploadResultImage'); button.disabled = true; button.textContent = '正在导入…'; $('#resultReviewStatus').textContent = '正在校验图片并生成本地缩略图…';
    try {
      const response = await creativeJson(`/api/creative/projects/${encodeURIComponent(creativeState.project.project_id)}/results?filename=${encodeURIComponent(file.name)}`, {method:'POST', headers:{'Content-Type':file.type || 'application/octet-stream'}, body:file});
      creativeState.project = response.project; const index = creativeState.projects.findIndex(project => project.project_id === response.project.project_id); if (index >= 0) creativeState.projects[index] = response.project;
      $('#resultImageFile').value = ''; renderCreativeProject(); $('#resultReviewStatus').textContent = `已导入 ${response.asset.filename}；图片只保存在本机。`;
    } finally { button.disabled = false; button.textContent = '导入结果图'; }
  }

  async function updateDatasetAsset(assetId, values, message) {
    await saveCreative();
    const response = await creativeJson(`/api/creative/projects/${encodeURIComponent(creativeState.project.project_id)}/results/${encodeURIComponent(assetId)}/dataset`, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({profile_id:creativeState.datasetProfile, ...values})});
    creativeState.project = response.project; const index = creativeState.projects.findIndex(project => project.project_id === response.project.project_id); if (index >= 0) creativeState.projects[index] = response.project;
    creativeState.datasetMessageProjectId = response.project.project_id; creativeState.datasetMessage = message; renderResultGallery(); renderCreativeProjects(); await refreshProjectJourney();
  }

  async function toggleDatasetAsset(assetId) {
    const asset = (creativeState.project?.generation?.result_assets || []).find(item => item.asset_id === assetId); if (!asset) return;
    const selected = asset.dataset_selected !== true;
    await updateDatasetAsset(assetId, {selected}, selected ? '已加入精选；导出时会包含原图与说明文件。' : '已移出精选；原始结果图仍保留在项目中。');
  }

  async function saveDatasetCaption(assetId) {
    const input = document.querySelector(`[data-dataset-caption="${CSS.escape(assetId)}"]`); if (!input) return;
    const hasCaption = Boolean(input.value.trim());
    await updateDatasetAsset(assetId, {caption_override:input.value}, hasCaption ? '已保存这张图当前格式的说明文字。' : '已清除单图修改；导出时使用项目生成的说明文字。');
  }

  function wd14Payload() {
    const general = Number($('#wd14GeneralThreshold').value); const character = Number($('#wd14CharacterThreshold').value);
    if (!Number.isFinite(general) || general < 0 || general > 1 || !Number.isFinite(character) || character < 0 || character > 1) throw new Error('WD14 阈值必须在 0 到 1 之间');
    return {general_threshold:general, character_threshold:character, limit:80};
  }

  function applyDatasetProject(project, message) {
    creativeState.project = project; const index = creativeState.projects.findIndex(item => item.project_id === project.project_id); if (index >= 0) creativeState.projects[index] = project;
    creativeState.datasetMessageProjectId = project.project_id; creativeState.datasetMessage = message; renderResultGallery(); renderCreativeProjects();
  }

  async function tagResultAsset(assetId) {
    await saveCreative(); const button = document.querySelector(`[data-wd14-tag="${CSS.escape(assetId)}"]`); if (button) { button.disabled = true; button.textContent = 'WD14 打标中…'; }
    creativeState.datasetMessageProjectId = creativeState.project.project_id; creativeState.datasetMessage = '正在本机使用 WD14 分析图片…'; $('#datasetExportStatus').textContent = creativeState.datasetMessage;
    try {
      const response = await creativeJson(`/api/creative/projects/${encodeURIComponent(creativeState.project.project_id)}/results/${encodeURIComponent(assetId)}/tag`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(wd14Payload())});
      applyDatasetProject(response.project, `WD14 已生成 ${response.asset.wd14_tagging?.general?.length || 0} 个 general 标签；请审核后确认。`);
    } finally { if (button) { button.disabled = false; button.textContent = '用 WD14 生成标签'; } }
  }

  async function tagSelectedDataset() {
    await saveCreative(); const button = $('#tagSelectedDataset'); button.disabled = true; button.textContent = '精选图片打标中…';
    creativeState.datasetMessageProjectId = creativeState.project.project_id; creativeState.datasetMessage = '正在逐张处理精选图片，请保持页面打开…'; $('#datasetExportStatus').textContent = creativeState.datasetMessage;
    try {
      const response = await creativeJson(`/api/creative/projects/${encodeURIComponent(creativeState.project.project_id)}/dataset-tag`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(wd14Payload())});
      const suffix = response.failed_count ? `；${response.failed_count} 张失败，可单独重试` : '';
      applyDatasetProject(response.project, `WD14 已完成 ${response.tagged_count}/${response.selected_count} 张${suffix}。`);
    } finally { button.textContent = '打标全部精选'; renderResultGallery(); }
  }

  async function saveWd14Review(assetId, confirmAnima) {
    const input = document.querySelector(`[data-wd14-draft="${CSS.escape(assetId)}"]`); if (!input) return;
    await saveCreative(); const response = await creativeJson(`/api/creative/projects/${encodeURIComponent(creativeState.project.project_id)}/results/${encodeURIComponent(assetId)}/tag-review`, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({draft_tags:input.value, confirm_anima:confirmAnima})});
    applyDatasetProject(response.project, confirmAnima ? '已确认写入此图的 Anima 标签；Krea 2 图片说明没有变化。' : '已保存 WD14 审核草稿，尚未改变导出时使用的标签。');
  }

  async function exportDataset() {
    await saveCreative(); const button = $('#exportDataset'); button.disabled = true; button.textContent = '正在打包…';
    try {
      const response = await creativeJson(`/api/creative/projects/${encodeURIComponent(creativeState.project.project_id)}/dataset-export`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({profile_id:creativeState.datasetProfile})});
      creativeState.datasetMessageProjectId = creativeState.project.project_id; creativeState.datasetMessage = `已导出 ${response.item_count} 张，文件保存在本机 exports/datasets。`; renderResultGallery();
      const link = document.createElement('a'); link.href = response.download_url; link.download = response.filename; document.body.appendChild(link); link.click(); link.remove();
    } finally { button.textContent = '导出精选数据集 ZIP'; renderResultGallery(); }
  }

  async function analyzeResultAsset(assetId) {
    const model = $('#visionModel').value; if (!model) throw new Error('没有可用的本地视觉模型');
    const buttons = [...document.querySelectorAll('[data-review-asset]')]; buttons.forEach(button => { button.disabled = true; });
    $('#resultReviewStatus').textContent = `正在由 ${model} 分析图片；本地大模型通常需要约 1–3 分钟，外部模型通常更快…`;
    try {
      creativeState.review = await creativeJson(`/api/creative/projects/${encodeURIComponent(creativeState.project.project_id)}/results/${encodeURIComponent(assetId)}/analyze`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({model})});
      creativeState.reviewAssetId = assetId; creativeState.reviewProjectId = creativeState.project.project_id; renderReviewProposal(); $('#resultReviewStatus').textContent = '图片分析已经完成，当前只是预览；请确认是否保存到项目。';
    } finally { buttons.forEach(button => { button.disabled = false; }); }
  }

  async function applyResultReview(fillEmptySlots) {
    if (!creativeState.review || !creativeState.reviewAssetId) return;
    const updated = await creativeJson(`/api/creative/projects/${encodeURIComponent(creativeState.project.project_id)}/results/${encodeURIComponent(creativeState.reviewAssetId)}/apply`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({analysis:creativeState.review, fill_empty_slots:fillEmptySlots})});
    creativeState.project = updated; const index = creativeState.projects.findIndex(project => project.project_id === updated.project_id); if (index >= 0) creativeState.projects[index] = updated; renderCreativeProject(); $('#resultReviewStatus').textContent = fillEmptySlots ? '已补充空白且未锁定的部分，并写入实测备注。' : '已把图片分析写入实测备注；画面设置没有变化。';
  }

  async function branchResultReview() {
    if (!creativeState.review || !creativeState.reviewAssetId || !creativeState.project) return;
    await saveCreative(); const parentProjectId = creativeState.project.project_id;
    $('#resultReviewStatus').textContent = '正在创建下一版项目；旧项目不会改变…';
    const nextProject = await creativeJson(`/api/creative/projects/${encodeURIComponent(parentProjectId)}/results/${encodeURIComponent(creativeState.reviewAssetId)}/branch`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({analysis:creativeState.review})});
    creativeState.projects.unshift(nextProject); creativeState.project = nextProject; creativeState.review = null; creativeState.reviewAssetId = ''; creativeState.reviewProjectId = ''; creativeState.sourcing = null; creativeState.sourcingProjectId = ''; renderCreativeProject(); $('#resultReviewStatus').textContent = `已创建第 ${iterationOf(nextProject)} 版；旧结果图没有复制，请根据修改说明开始调整。`;
  }

  async function applyIterationSuggestions() {
    if (!creativeState.project?.project_id) return;
    await saveCreative(); const button = $('#applyIterationSuggestions'); button.disabled = true; button.textContent = '正在填入…';
    const response = await creativeJson(`/api/creative/projects/${encodeURIComponent(creativeState.project.project_id)}/iteration/apply`, {method:'POST'});
    creativeState.project = response.project; creativeState.iteration = response.iteration; creativeState.iterationProjectId = response.project.project_id; creativeState.iterationMessageProjectId = response.project.project_id; creativeState.iterationMessage = response.applied_slots.length ? `已填入：${response.applied_slots.map(slot => slotsMeta[slot]?.[0] || slot).join('、')}。` : '没有可填入的槽位；锁定和已有内容均保持不变。';
    const index = creativeState.projects.findIndex(project => project.project_id === response.project.project_id); if (index >= 0) creativeState.projects[index] = response.project;
    renderCreativeProject();
  }

  async function startFromCharacter(item) {
    const detail = await creativeJson('/api/oc-manager/characters/' + encodeURIComponent(item.character_id)); await ensureCreativeProject();
    const traits = [detail.name, detail.gender, detail.age ? `${detail.age} years old` : '', detail.race, detail.identity].filter(Boolean);
    const project = collectCreative(); project.title = `${detail.name} · 绘图项目`; project.character_id = detail.character_id; project.slots.character = traits.join(', ');
    if (detail.prompts?.length) project.slots.style = [project.slots.style, detail.prompts.map(p => p.text).join(', ')].filter(Boolean).join(', ');
    const gallery = Array.isArray(detail.profile?.gallery) ? detail.profile.gallery : [];
    project.references.push({key:`oc:${detail.character_id}`, slot:'character', source_id:'oc-manager', external_id:detail.character_id, title:detail.name, kind:'character', visuals:gallery.filter(v => v && (v.thumbnail_url || v.url)).map(v => ({thumbnail_url:v.thumbnail_url || v.url, original_url:v.original_url || v.url}))});
    creativeState.project = project; renderCreativeProject(); await saveCreative(); await setView('creative');
  }

  function showCreativeError(error) { $('#creativeSaveState').textContent = `操作失败：${error.message}`; console.error(error); }
  function showResultReviewError(error) { $('#resultReviewStatus').textContent = `结果图操作失败：${error.message}`; $('#datasetExportStatus').textContent = `操作失败：${error.message}`; showCreativeError(error); }

  $('#creativeSlots').innerHTML = slotTemplate();
  $('#refreshProjectJourney').addEventListener('click',()=>refreshProjectJourney().catch(showCreativeError));
  $('#projectJourneyGrid').addEventListener('click',event=>{ const button=event.target.closest('[data-journey-action]'); if(!button) return; const stage=button.dataset.journeyAction,view=button.dataset.journeyView,target=button.dataset.journeyTarget; if(stage==='dataset'&&!target) { syncProjectDataset().catch(showCreativeError); return; } window.setPromptHubView?.(view).then(()=>{ if(view==='datasets'&&target) return window.openDatasetWorkspace?.(target,stage==='delivery'?5:0); const targets={inspiration:'#creativeBrief',prompts:'.output-rail',generation:'.workflow-dispatch',results:'#creativeResultsSection'}; document.querySelector(targets[stage]||'.creative-editor')?.scrollIntoView({behavior:'smooth',block:'start'}); }).catch(showCreativeError); });
  $('#newCreativeProject').addEventListener('click', () => createCreativeProject().catch(showCreativeError));
  ['creativeTitle','creativeBrief','creativeSafety','creativeNotes','genSteps','genCfg','genSeed','genResults'].forEach(id => $('#' + id).addEventListener('input', queueCreativeSave));
  $('#creativeSlots').addEventListener('input', queueCreativeSave);
  $('#creativeSlots').addEventListener('click', event => { const button = event.target.closest('[data-lock-slot]'); if (!button || !creativeState.project) return; creativeState.project = collectCreative(); const key = button.dataset.lockSlot; creativeState.project.slot_locks[key] = !creativeState.project.slot_locks[key]; renderCreativeProject(); queueCreativeSave(); });
  $('#creativeReferences').addEventListener('click', event => { const button = event.target.closest('[data-remove-reference]'); if (!button) return; creativeState.project.references.splice(Number(button.dataset.removeReference), 1); renderCreativeReferences(); queueCreativeSave(); });
  $('#creativeProjectList').addEventListener('click', async event => { const button = event.target.closest('[data-project-id]'); if (!button || button.dataset.projectId === creativeState.project?.project_id) return; try { clearTimeout(creativeState.saveTimer); await saveCreative(); creativeState.project = creativeState.projects.find(p => p.project_id === button.dataset.projectId); creativeState.review = null; creativeState.reviewProjectId = ''; renderCreativeProject(); } catch(error) { showCreativeError(error); } });
  $('#sourceCreative').addEventListener('click', () => runCreativeSourcing().catch(showCreativeError));
  $('#closeSourcing').addEventListener('click', () => { $('#sourcingPanel').hidden = true; });
  $('#sourcingGroups').addEventListener('click', async event => { const button = event.target.closest('[data-source-slot]'); if (!button || !creativeState.sourcing) return; const group = creativeState.sourcing.slots?.[button.dataset.sourceSlot]; const item = group?.candidates?.[Number(button.dataset.sourceIndex)]; if (!item) return; try { await addEntryToCreative(item, button.dataset.sourceSlot); renderSourcing(); } catch(error) { showCreativeError(error); } });
  $('#creativeBrief').addEventListener('input', () => { if (creativeState.sourcing) $('#sourcingRailStatus').textContent = '创作想法已变化，请重新取材。'; });
  $('#visionModel').addEventListener('change', updateVisionHint);
  $('#uploadResultImage').addEventListener('click', () => uploadResultImage().catch(showResultReviewError));
  $('#datasetProfile').addEventListener('change', event => { creativeState.datasetProfile = event.target.value; creativeState.datasetMessage = ''; renderResultGallery(); });
  $('#tagSelectedDataset').addEventListener('click', () => tagSelectedDataset().catch(showResultReviewError));
  $('#exportDataset').addEventListener('click', () => exportDataset().catch(showResultReviewError));
  $('#resultGallery').addEventListener('input', event => { const input = event.target.closest('[data-wd14-draft]'); if (!input) return; const asset = (creativeState.project?.generation?.result_assets || []).find(item => item.asset_id === input.dataset.wd14Draft); if (asset?.wd14_tagging) asset.wd14_tagging.draft_tags = input.value; });
  $('#resultGallery').addEventListener('click', event => {
    const language = event.target.closest('[data-toggle-tag-language]'); if (language) { window.toggleTagDisplayLanguage?.(); return; }
    const chip = event.target.closest('[data-wd14-chip]'); if (chip) { toggleWd14Chip(chip.dataset.wd14Chip, chip.dataset.tagValue); return; }
    const toggle = event.target.closest('[data-dataset-toggle]'); if (toggle) { toggleDatasetAsset(toggle.dataset.datasetToggle).catch(showResultReviewError); return; }
    const tag = event.target.closest('[data-wd14-tag]'); if (tag) { tagResultAsset(tag.dataset.wd14Tag).catch(showResultReviewError); return; }
    const saveTags = event.target.closest('[data-save-wd14]'); if (saveTags) { saveWd14Review(saveTags.dataset.saveWd14, false).catch(showResultReviewError); return; }
    const confirmTags = event.target.closest('[data-confirm-wd14]'); if (confirmTags) { saveWd14Review(confirmTags.dataset.confirmWd14, true).catch(showResultReviewError); return; }
    const saveCaption = event.target.closest('[data-save-caption]'); if (saveCaption) { saveDatasetCaption(saveCaption.dataset.saveCaption).catch(showResultReviewError); return; }
    const review = event.target.closest('[data-review-asset]'); if (review) analyzeResultAsset(review.dataset.reviewAsset).catch(showResultReviewError);
  });
  window.addEventListener('tag-language-change', renderResultGallery);
  $('#applyReviewSlots').addEventListener('click', () => applyResultReview(true).catch(showResultReviewError));
  $('#applyReviewNotes').addEventListener('click', () => applyResultReview(false).catch(showResultReviewError));
  $('#branchReview').addEventListener('click', () => branchResultReview().catch(showResultReviewError));
  $('#applyIterationSuggestions').addEventListener('click', () => applyIterationSuggestions().catch(showCreativeError));
  $('#closeReview').addEventListener('click', () => { creativeState.review = null; $('#reviewProposal').hidden = true; });
  document.querySelectorAll('[data-profile]').forEach(button => button.addEventListener('click', () => { creativeState.profile = button.dataset.profile; creativeState.project.target_profile = creativeState.profile; document.querySelectorAll('[data-profile]').forEach(b => b.classList.toggle('active', b === button)); renderOutput(); renderWorkflowProfiles(); queueCreativeSave(); }));
  $('#workflowProfile').addEventListener('change',()=>{ creativeState.workflowLoraPickerOpen=false; creativeState.workflowLoraQuery=''; creativeState.workflowLoraFolder=''; renderWorkflowProfiles(); });
  $('#workflowLowCost').addEventListener('change', renderWorkflowProfiles);
  $('#workflowControlList').addEventListener('change',()=>{ saveWorkflowControlsFromForm(); renderWorkflowControls(); });
  $('#workflowSampler').addEventListener('change',saveWorkflowControlsFromForm);
  $('#workflowScheduler').addEventListener('change',saveWorkflowControlsFromForm);
  $('#workflowLoraRows').addEventListener('change',saveWorkflowControlsFromForm);
  $('#workflowLoraRows').addEventListener('click',event=>{ const button=event.target.closest('[data-workflow-lora-remove]'); if(!button) return; const profile=selectedWorkflowProfile(); if(!profile) return; const stored=storedWorkflowControls(profile.profile_id),loras=Array.isArray(stored.loras)?stored.loras.slice():[]; loras.splice(Number(button.dataset.workflowLoraRemove),1); const all={...(creativeState.project.generation?.workflow_controls||{})}; all[profile.profile_id]={...stored,loras}; creativeState.project.generation={...(creativeState.project.generation||{}),workflow_controls:all}; renderWorkflowControls(); queueCreativeSave(); });
  $('#workflowAddLora').addEventListener('click',()=>{ creativeState.workflowLoraPickerOpen=!creativeState.workflowLoraPickerOpen; renderWorkflowControls(); if(creativeState.workflowLoraPickerOpen) queueMicrotask(()=>$('#workflowLoraSearch').focus()); });
  $('#workflowLoraPickerClose').addEventListener('click',()=>{ creativeState.workflowLoraPickerOpen=false; $('#workflowLoraPicker').hidden=true; });
  $('#workflowLoraSearch').addEventListener('input',event=>{ creativeState.workflowLoraQuery=event.target.value; const profile=selectedWorkflowProfile(); if(profile) renderWorkflowLoraPicker(profile,new Set((storedWorkflowControls(profile.profile_id).loras||[]).map(item=>item.lora_id))); });
  $('#workflowLoraFolder').addEventListener('change',event=>{ creativeState.workflowLoraFolder=event.target.value; const profile=selectedWorkflowProfile(); if(profile) renderWorkflowLoraPicker(profile,new Set((storedWorkflowControls(profile.profile_id).loras||[]).map(item=>item.lora_id))); });
  $('#workflowLoraResults').addEventListener('click',event=>{ const button=event.target.closest('[data-workflow-lora-pick]'),profile=selectedWorkflowProfile(); if(!button||!profile) return; const stored=storedWorkflowControls(profile.profile_id),loras=Array.isArray(stored.loras)?stored.loras.slice():[],loraId=button.dataset.workflowLoraPick; if(loras.some(item=>item.lora_id===loraId)||loras.length>=Number(profile.controls?.max_additional_loras||4)) return; loras.push({lora_id:loraId,strength:0.8}); const all={...(creativeState.project.generation?.workflow_controls||{})}; all[profile.profile_id]={...stored,loras}; creativeState.project.generation={...(creativeState.project.generation||{}),workflow_controls:all}; renderWorkflowControls(); queueCreativeSave(); });
  $('#sendWorkflow').addEventListener('click', () => sendWorkflowProfile().catch(showCreativeError));
  document.querySelectorAll('[data-copy-output]').forEach(button => button.addEventListener('click', async () => { const text = creativeState.outputs[creativeState.profile]?.[button.dataset.copyOutput] || ''; await navigator.clipboard.writeText(text); button.textContent = '已复制'; setTimeout(() => {button.textContent = '复制';}, 1200); }));
  $('#saveRecipe').addEventListener('click', async () => { try { await saveCreative(); const recipe = await creativeJson('/api/creative/recipes', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({project_id:creativeState.project.project_id, name:$('#recipeName').value.trim()})}); creativeState.recipes.unshift(recipe); renderCreativeRecipes(); $('#recipeName').value=''; $('#creativeSaveState').textContent='配方已保存'; } catch (error) { showCreativeError(error); } });
  $('#creativeRecipeList').addEventListener('click', event => { const button = event.target.closest('[data-recipe-id]'); if (!button) return; const recipe = creativeState.recipes.find(r => r.recipe_id === button.dataset.recipeId); if (!recipe?.snapshot?.project) return; const keep = {project_id:creativeState.project.project_id, created_at:creativeState.project.created_at}; creativeState.project = {...recipe.snapshot.project, ...keep}; renderCreativeProject(); queueCreativeSave(); });
  $('#exportCreative').addEventListener('click', async () => { try { await saveCreative(); const data = await creativeJson(`/api/creative/projects/${encodeURIComponent(creativeState.project.project_id)}/export`); const blob = new Blob([JSON.stringify(data, null, 2)], {type:'application/json'}); const link = document.createElement('a'); link.href=URL.createObjectURL(blob); link.download=(creativeState.project.title || 'creative-project').replace(/[\\/:*?"<>|]/g,'-') + '.json'; link.click(); URL.revokeObjectURL(link.href); $('#creativeSaveState').textContent='双格式 JSON 已导出'; } catch(error) { showCreativeError(error); } });
  $('#assistCreative').addEventListener('click', async () => { try { const payload=collectCreative(); if (!payload.brief_zh) throw new Error('请先写一段中文创作想法'); $('#assistCreative').disabled=true; $('#assistCreative').textContent='所选模型正在补全…'; creativeState.suggestion=await creativeJson('/api/creative/assist',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({brief:payload.brief_zh,slots:payload.slots,slot_locks:payload.slot_locks,model:$('#lmModel').value,target_profile:creativeState.profile})}); $('#assistPreview').textContent=JSON.stringify(creativeState.suggestion.suggested_slots,null,2); $('#assistProposal').hidden=false; } catch(error) { showCreativeError(error); } finally { $('#assistCreative').disabled=false; $('#assistCreative').textContent='用所选模型补全空白项'; } });
  $('#applyAssist').addEventListener('click', () => { if (!creativeState.suggestion) return; creativeState.project.slots=creativeState.suggestion.suggested_slots; creativeState.suggestion=null; $('#assistProposal').hidden=true; renderCreativeProject(); queueCreativeSave(); });
  $('#cancelAssist').addEventListener('click', () => { creativeState.suggestion=null; $('#assistProposal').hidden=true; });
  $('#discoverExternalModels').addEventListener('click', () => discoverExternalModels().catch(showCreativeError));
  $('#saveExternalModel').addEventListener('click', () => saveExternalModel().catch(showCreativeError));
  $('#cancelExternalModelEdit').addEventListener('click', () => { clearExternalModelForm(); $('#externalModelStatus').textContent='已取消编辑。'; });
  $('#externalModelCandidates').addEventListener('click', event => { const button=event.target.closest('[data-use-external-model]'); if(!button) return; $('#externalModelName').value=button.dataset.useExternalModel; $('#externalModelStatus').textContent='已填入模型名称。确认是否支持看图，然后保存。'; });
  $('#externalModelList').addEventListener('click', event => { const editButton=event.target.closest('[data-edit-external-model]'); if(editButton) { editExternalModel(editButton.dataset.editExternalModel); return; } const deleteButton=event.target.closest('[data-delete-external-model]'); if(deleteButton) deleteExternalModel(deleteButton.dataset.deleteExternalModel).catch(showCreativeError); });

  $('#results').addEventListener('click', event => {
    const add = event.target.closest('[data-creative-add]'); if (add) { const card=add.closest('[data-result-index]'); const item=currentResults[Number(card.dataset.resultIndex)]; const slot=card.querySelector('[data-creative-slot]').value; addEntryToCreative(item,slot).catch(showCreativeError); return; }
    const fromOc = event.target.closest('[data-character-create]'); if (fromOc) { const card=fromOc.closest('[data-character-index]'); startFromCharacter(currentCharacters[Number(card.dataset.characterIndex)]).catch(showCreativeError); }
  });
})();
</script>
"""
