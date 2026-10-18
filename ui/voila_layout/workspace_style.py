"""Shared, local-only visual tokens for the scientific workspace."""

WORKSPACE_CSS = """
<style>
.cochem-accessible {
  --cc-ink: #172c36; --cc-muted: #4c616a; --cc-accent: #006b68;
  --cc-accent-soft: #eaf5f3; --cc-line: #cedbdc; --cc-surface: #fff;
  --cc-canvas: #f4f7f7; --cc-error: #922d32; --cc-focus: #936000;
  color: var(--cc-ink); background: var(--cc-canvas);
  font: 15px/1.6 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  width: 100%; max-width: 1440px; margin: 0 auto; border: 1px solid var(--cc-line);
}
.cochem-accessible *, .cochem-accessible *::before, .cochem-accessible *::after {box-sizing: border-box;}
.cochem-accessible .widget-box, .cochem-accessible .widget-html,
.cochem-accessible .widget-inline-hbox {min-width: 0; max-width: 100%;}
.cochem-accessible .widget-html-content {line-height: 1.6; overflow-wrap: anywhere;}
.cochem-accessible .widget-html-content:empty {display: none;}
.cochem-accessible h1, .cochem-accessible h2, .cochem-accessible h3,
.cochem-accessible h4 {color: var(--cc-ink); line-height: 1.3; font-weight: 650;}
.cochem-accessible h1 {font-size: 23px; margin: 0; letter-spacing: -.4px;}
.cochem-accessible h2 {font-size: 25px; margin: 0 0 8px; letter-spacing: -.4px;}
.cochem-accessible h3 {font-size: 17px; margin: 0 0 8px;}
.cochem-accessible h4 {font-size: 15px; margin: 8px 0;}
.cochem-accessible p {margin: 4px 0 12px; max-width: 80ch;}
.cochem-accessible a {color: var(--cc-accent); text-decoration: underline; text-underline-offset: 3px;}
.cochem-accessible .cochem-header {background: var(--cc-surface); border: 0 !important;
  border-bottom: 1px solid var(--cc-line) !important; padding: 16px 24px !important; gap: 24px;}
.cochem-accessible .cochem-brand p {font-size: 12px; color: var(--cc-muted); margin: 0;}
.cochem-accessible .cochem-status {font-size: 13px; color: var(--cc-muted);}
.cochem-accessible .cochem-status strong {color: var(--cc-ink);}
.cochem-accessible .cochem-navigation {background: var(--cc-canvas); border: 0 !important;
  padding: 24px 12px !important; gap: 4px; align-self: stretch;}
.cochem-accessible .cochem-nav-label {color: var(--cc-muted); font-size: 11px;
  font-weight: 650; letter-spacing: .08em; padding: 0 12px; margin: 12px 0 4px;}
.cochem-accessible .cochem-navigation .jupyter-button {background: transparent; border: 0;
  border-left: 3px solid transparent; border-radius: 0 4px 4px 0; text-align: left;
  padding: 10px 12px; margin: 0 !important; width: 100%; font-weight: 500;}
.cochem-accessible .cochem-navigation .jupyter-button.mod-primary {background: var(--cc-accent-soft);
  border-left-color: var(--cc-accent); color: #005551; font-weight: 650;}
.cochem-accessible .cochem-page {background: var(--cc-surface); padding: 28px 32px !important;
  width: 100%; min-height: 560px; gap: 20px;}
.cochem-accessible .cochem-page-heading {margin-bottom: 0;}
.cochem-accessible .cochem-page-heading p {color: var(--cc-muted);}
.cochem-accessible .cochem-section {border: 0; border-top: 1px solid var(--cc-line);
  padding: 20px 0 0; gap: 8px; width: 100%;}
.cochem-accessible .cochem-section:first-child {border-top: 0;}
.cochem-accessible .cochem-hint {color: var(--cc-muted); font-size: 14px;}
.cochem-accessible .cochem-hint p {margin: 0 0 8px;}
.cochem-accessible .cochem-steps {display: flex; gap: 20px; list-style: none; margin: 0; padding: 0;}
.cochem-accessible .cochem-steps li {flex: 1; border-top: 3px solid #a7c6c4; padding-top: 8px;}
.cochem-accessible .cochem-steps strong {display: block; font-size: 14px;}
.cochem-accessible .cochem-steps span {color: var(--cc-muted); font-size: 13px;}
.cochem-accessible .widget-hbox {flex-wrap: wrap; gap: 12px; align-items: flex-start;}
.cochem-accessible .widget-inline-hbox {height: auto; margin: 4px 0;}
.cochem-accessible .widget-inline-hbox:not(.widget-html) {min-height: 36px;}
.cochem-accessible .cochem-style-host {display: none;}
.cochem-accessible .widget-html:has(> .widget-html-content:empty) {display: none;}
.cochem-accessible .widget-label {color: var(--cc-ink); font-size: 14px;
  white-space: normal; height: auto; line-height: 1.5;}
.cochem-accessible input, .cochem-accessible select, .cochem-accessible textarea {
  color: var(--cc-ink); background: #fff; border: 1px solid #82999e; border-radius: 4px;
  font-family: inherit; font-size: 14px; min-width: 0; line-height: 1.5;}
.cochem-accessible select, .cochem-accessible input:not([type=checkbox]):not([type=radio]) {min-height: 36px;}
.cochem-accessible select:disabled, .cochem-accessible input:disabled {color: #5c6a70; background: #f0f3f3;}
.cochem-accessible .jupyter-button {color: var(--cc-ink); background: #fff; border: 1px solid #9aafb3;
  border-radius: 4px; box-shadow: none; font: 600 14px/1.5 system-ui, sans-serif;
  width: auto; min-height: 38px; height: auto; white-space: normal; overflow-wrap: anywhere; padding: 8px 14px;}
.cochem-accessible .jupyter-button:hover:enabled {background: #eaf1f1;}
.cochem-accessible .jupyter-button.mod-primary, .cochem-accessible .jupyter-button.mod-success,
.cochem-accessible .jupyter-button.mod-info {color: #fff; background: var(--cc-accent); border-color: var(--cc-accent);}
.cochem-accessible .jupyter-button.mod-primary:hover:enabled,
.cochem-accessible .jupyter-button.mod-success:hover:enabled,
.cochem-accessible .jupyter-button.mod-info:hover:enabled {background: #005551;}
.cochem-accessible .cochem-navigation .jupyter-button.mod-primary:hover:enabled {
  color: #005551; background: #dcecea;}
.cochem-accessible .jupyter-button.mod-danger {color: #fff; background: var(--cc-error); border-color: var(--cc-error);}
.cochem-accessible .jupyter-button.mod-warning {color: var(--cc-ink); background: #fff6da;}
.cochem-accessible .jupyter-button:disabled {color: #5b6b71; background: #edf1f2; border-color: #ccd6d9; opacity: 1;}
.cochem-accessible .cochem-disclosure {border-top: 1px solid var(--cc-line); padding: 4px 0;}
.cochem-accessible .cochem-disclosure-toggle.jupyter-button {border: 0; text-align: left;
  color: var(--cc-accent); background: transparent; font-weight: 600; padding: 8px 0;}
.cochem-accessible .cochem-disclosure-body {border-left: 2px solid #a7c6c4; padding: 8px 0 8px 16px; gap: 8px;}
.cochem-accessible details {margin: 8px 0; max-width: 85ch;}
.cochem-accessible summary {cursor: pointer; color: var(--cc-accent); font-weight: 600;
  padding: 6px 0; min-height: 32px;}
.cochem-accessible details[open] > summary {margin-bottom: 8px;}
.cochem-accessible details p, .cochem-accessible details ul {font-size: 14px;}
.cochem-accessible .cochem-help {border-left: 2px solid #bfd6d4; padding-left: 12px;}
.cochem-accessible .cochem-selection {background: #edf5f4; border-left: 3px solid var(--cc-accent);
  padding: 12px 16px; font-size: 14px;}
.cochem-accessible .cochem-selection p {margin: 0;}
.cochem-accessible .cochem-actions {gap: 12px; padding-top: 8px;}
.cochem-accessible .jupyter-widgets.jupyter-widget-tab > .widget-tab-bar {height: auto; min-height: 40px; overflow: visible;}
.cochem-accessible .jupyter-widgets.jupyter-widget-tab > .widget-tab-bar :is(.p-TabBar-content, .lm-TabBar-content) {flex-wrap: wrap; gap: 4px;}
.cochem-accessible .jupyter-widgets.jupyter-widget-tab > .widget-tab-bar :is(.p-TabBar-tab, .lm-TabBar-tab) {height: auto; min-height: 40px;
  flex: 1 1 144px; min-width: 0; padding: 8px 12px; border-color: var(--cc-line);
  color: var(--cc-muted); background: #f4f7f7;}
.cochem-accessible .jupyter-widgets.jupyter-widget-tab > .widget-tab-bar :is(.p-TabBar-tabLabel, .lm-TabBar-tabLabel) {
  white-space: normal; overflow: visible; text-overflow: clip; line-height: 1.5;}
.cochem-accessible .jupyter-widgets.jupyter-widget-tab > .widget-tab-bar :is(.p-TabBar-tab.p-mod-current, .lm-TabBar-tab.lm-mod-current) {
  color: #005551; border-top: 3px solid var(--cc-accent); background: #fff; font-weight: 650;}
.cochem-accessible .widget-tab-contents {padding: 20px 16px; border-color: var(--cc-line);}
.cochem-accessible table {border-collapse: collapse; font-size: 14px; max-width: 100%;}
.cochem-accessible th, .cochem-accessible td {padding: 8px 12px; text-align: left; border: 1px solid var(--cc-line);}
.cochem-accessible th {background: #eef4f4; font-weight: 650;}
.cochem-accessible caption {text-align: left; font-weight: 650; margin-bottom: 8px;}
.cochem-accessible pre {white-space: pre-wrap; overflow-wrap: anywhere; font-size: 12px;}
.cochem-accessible .cochem-footer {padding: 0 24px 16px !important; border: 0 !important;
  min-height: 0 !important; background: #fff;}
.cochem-accessible .cochem-error {border-left: 4px solid var(--cc-error); background: #fff1ef;
  padding: 12px 16px; color: #63272b;}
.cochem-accessible :is(button, input, select, textarea, summary, a):focus-visible {
  outline: 3px solid var(--cc-focus); outline-offset: 3px;}
@media (max-width: 900px) {
  .cochem-accessible .cochem-mainlayout {display: flex !important; flex-direction: column; gap: 0;}
  .cochem-accessible .cochem-navigation {width: 100% !important; flex-flow: row wrap; padding: 8px !important;}
  .cochem-accessible .cochem-navigation > .widget-html {display: none;}
  .cochem-accessible .cochem-navigation .jupyter-button {flex: 1 1 140px; width: auto;}
  .cochem-accessible .cochem-nav-label {display: none;}
  .cochem-accessible .cochem-page {padding: 20px !important;}
  .cochem-accessible .cochem-structure-columns {flex-direction: column;}
  .cochem-accessible .cochem-structure-columns > .widget-box {width: 100% !important; padding: 0 !important;}
}
@media (max-width: 600px) {
  .cochem-accessible .cochem-header {padding: 12px !important; gap: 8px;}
  .cochem-accessible .cochem-page {padding: 16px 12px !important;}
  .cochem-accessible .cochem-steps {display: block;}
  .cochem-accessible .cochem-steps li {margin-bottom: 8px;}
  .cochem-accessible .widget-inline-hbox {flex-wrap: wrap; width: 100% !important;}
  .cochem-accessible .widget-inline-hbox > .widget-label {width: 100% !important; text-align: left; margin: 0 0 4px;}
  .cochem-accessible .widget-inline-hbox > :is(select,input,textarea) {width: 100%;}
  .cochem-accessible .widget-tab-contents {padding: 16px 8px;}
  .cochem-accessible .cochem-navigation .jupyter-button {flex-basis: 110px; font-size: 13px; padding: 8px;}
}
</style>
"""
