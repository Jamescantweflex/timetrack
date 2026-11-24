// TimeTrack menu-bar item. JavaScript for Automation: ships with macOS, no install.
// Run by launchd as:  osascript -l JavaScript menubar.js
// It only draws what http://127.0.0.1:8765/api/menubar returns.
ObjC.import('Cocoa');
const BASE = 'http://127.0.0.1:8765';
const app = $.NSApplication.sharedApplication;
app.setActivationPolicy($.NSApplicationActivationPolicyAccessory);
const item = $.NSStatusBar.systemStatusBar.statusItemWithLength($.NSVariableStatusItemLength);
item.button.title = $('…');

function getJSON(path) {
  const d = $.NSData.dataWithContentsOfURL($.NSURL.URLWithString(BASE + path));
  if (d.isNil()) return null;
  try { return JSON.parse(ObjC.unwrap($.NSString.alloc.initWithDataEncoding(d, $.NSUTF8StringEncoding))); }
  catch (e) { return null; }
}
function post(path, obj) {
  const req = $.NSMutableURLRequest.requestWithURL($.NSURL.URLWithString(BASE + path));
  req.HTTPMethod = $('POST');
  req.setValueForHTTPHeaderField($('application/json'), $('Content-Type'));
  req.setValueForHTTPHeaderField($('1'), $('X-TimeTrack'));
  req.HTTPBody = $(JSON.stringify(obj)).dataUsingEncoding($.NSUTF8StringEncoding);
  $.NSURLConnection.sendSynchronousRequestReturningResponseError(req, null, null);
}
function setSymbol(name) {
  const img = $.NSImage.imageWithSystemSymbolNameAccessibilityDescription($(name), $('TimeTrack'));
  if (!img.isNil()) { img.template = true; item.button.image = img; item.button.imagePosition = $.NSImageLeft; }
}

ObjC.registerSubclass({ name: 'TTMenuHandler', methods: {
  'tick:':      { types: ['void', ['id']], implementation: function (_) { refresh(); } },
  'open:':      { types: ['void', ['id']], implementation: function (_) { $.NSWorkspace.sharedWorkspace.openURL($.NSURL.URLWithString(BASE + '/')); } },
  'snooze:':    { types: ['void', ['id']], implementation: function (s) { post('/api/snooze', { minutes: Number(s.tag) }); refresh(); } },
} });
const handler = $.TTMenuHandler.alloc.init;

function add(menu, title, action, tag) {
  const mi = menu.addItemWithTitleActionKeyEquivalent($(title), action || null, $(''));
  if (action) { mi.target = handler; if (tag !== undefined) mi.tag = tag; } else { mi.enabled = false; }
  return mi;
}
function refresh() {
  const d = getJSON('/api/menubar');
  const menu = $.NSMenu.alloc.init;
  menu.autoenablesItems = false;
  if (!d) {
    item.button.title = $(' –'); setSymbol('hourglass');
    add(menu, 'TimeTrack is not running');
    add(menu, 'Run  zsh install.sh  in the timetrack folder');
  } else {
    item.button.title = $(' ' + d.title); setSymbol(d.symbol);
    d.lines.forEach(l => add(menu, l));
    menu.addItem($.NSMenuItem.separatorItem);
    add(menu, 'Open dashboard', 'open:');
    menu.addItem($.NSMenuItem.separatorItem);
    if (d.snoozed) add(menu, 'End snooze', 'snooze:', 0);
    add(menu, 'Snooze pause screens 30 min', 'snooze:', 30);
    add(menu, 'Snooze 1 hour', 'snooze:', 60);
    add(menu, 'Snooze 2 hours', 'snooze:', 120);
  }
  item.menu = menu;
}
refresh();
$.NSTimer.scheduledTimerWithTimeIntervalTargetSelectorUserInfoRepeats(20, handler, 'tick:', null, true);
app.run;
