# Qt/PySide6 Animation Flicker Research - Findings & Recommendations

## Problem Statement
Frameless translucent window (`WA_TranslucentBackground` + `FramelessWindowHint`) with animated collapsible drawer between fixed header and fixed bottom prompt area. Jitter/flicker occurs during drawer animation despite geometry being mostly stable.

## Findings from Qt Documentation

### 1. Official Qt Patterns for Collapsible Sections

**Source:** [Qt Forum - Expand/Collapse Animation](https://forum.qt.io/topic/127615/how-can-i-expand-and-collapse-part-of-my-form-with-qpropertyanimation)

**Key Finding:** Animate `maximumHeight` property, not widget size directly. This allows the layout to properly adjust spacing during animation.

**Quote:** "To create a collapsible middle section in a QVBoxLayout while keeping a bottom widget fixed, animate the **maximumHeight** property rather than the widget's size property."

**Documentation Link:** 
- [QPropertyAnimation Class](https://doc.qt.io/qt-6/qpropertyanimation.html)
- [Animation Framework Overview](https://doc.qt.io/qt-6/animation-overview.html)

### 2. Layout Animation Guidance

**Source:** [Qt Layout Management](https://doc.qt.io/qtforpython-6/overviews/qtwidgets-layout.html)

**Key Finding:** Layouts automatically reposition widgets during layout passes, which can conflict with animation properties. Standard layouts are not designed for smooth animations due to automatic geometry management.

**Recommendation:** Consider disabling layout updates during animation or using custom layouts with animation-aware properties.

**Documentation Link:**
- [QLayout Class](https://doc.qt.io/qt-6/qlayout.html)

### 3. FramelessWindowHint + WA_TranslucentBackground Caveats

**Source:** [Qt Shaped Clock Example](https://doc.qt.io/qt-6/qtwidgets-widgets-shapedclock-example.html)

**Key Finding:** Standard pattern for translucent frameless windows:
```cpp
setWindowFlags(Qt::FramelessWindowHint | Qt::WindowSystemMenuHint)
setAttribute(Qt::WA_TranslucentBackground)
```

**Windows DWM Issues:** 
- [Qt Windows Issues](https://doc.qt.io/qt-6/windows-issues.html) documents DWM composition problems with special window types
- Fullscreen OpenGL windows have known DWM issues, but translucent backgrounds can also be affected

**Documentation Links:**
- [Shaped Clock Example](https://doc.qt.io/qt-6/qtwidgets-widgets-shapedclock-example.html)
- [Qt Windows Specific Issues](https://doc.qt.io/qt-6/windows-issues.html)

### 4. Best Practices to Avoid Flicker

#### A. setUpdatesEnabled()

**Source:** [QWidget::setUpdatesEnabled](https://doc.qt.io/qt-6/qwidget.html#setUpdatesEnabled)

**Key Finding:** Disable updates during animation to prevent intermediate repaints:
```cpp
widget->setUpdatesEnabled(false);
// Perform animation
widget->setUpdatesEnabled(true);
```

**Important:** Setting `setUpdatesEnabled(false)` on a parent widget disables repainting for all children. Must re-enable after animation completes.

**Documentation Link:**
- [QWidget::updatesEnabled Property](https://doc.qt.io/qt-6/qwidget.html#updatesEnabled-prop)

#### B. WA_OpaquePaintEvent and WA_NoSystemBackground

**Source:** [Qt Forum Discussion](https://interest.qt-project.narkive.com/hT3hAMyq/wa-nosystembackground-vs-wa-opaquepaintevent)

**Key Findings:**
- `WA_OpaquePaintEvent`: Optimization hint - tells Qt your painting completely fills the widget
- `WA_NoSystemBackground`: Prevents Qt from filling widget with standard background before paintEvent
- When `WA_TranslucentBackground` is set, `WA_NoSystemBackground` is automatically enabled
- Setting both is common practice but `WA_OpaquePaintEvent` alone may suffice

**Note:** These are optimization hints, not guaranteed to eliminate flicker.

#### C. Avoiding setMask Per-Frame

**Source:** General Qt best practices

**Key Finding:** Calling `setMask()` frequently during animation is expensive. Set mask once before animation or use a fixed mask that doesn't change.

#### D. Double-Buffering

**Source:** [Qt Animation Flicker Issues](https://stackoverflow.com/questions/5847031/qt-animation-problem-flickering-geometry-animation)

**Key Finding:** Qt widgets are double-buffered by default. The flicker issue is more likely related to layout recalculation and repaint synchronization than buffering.

### 5. Qt Recommendations for Fixed Bottom Panes

**Source:** [Qt Forum - QSplitter Fixed Pane](https://forum.qt.io/topic/13869/how-to-make-the-size-of-a-widget-in-a-qsplitter-fixed-when-resizing-the-qsplitter)

**Key Finding:** Use `setStretchFactor()` to control which panes expand:
```cpp
splitter->setStretchFactor(0, 0);  // Fixed pane
splitter->setStretchFactor(1, 1);  // Expandable pane
```

**Alternative:** For non-splitter layouts, use `QSizePolicy::Fixed` for the bottom widget and ensure it's not affected by layout recalculation during animation.

### 6. Platform-Specific Notes for Windows DWM

**Source:** [Qt Bug Report QTBUG-89688](https://bugreports.qt.io/browse/QTBUG-89688)

**Key Finding:** 
- Windows DWM composition can cause flickering during window resize animations
- Issue was fixed in Qt 6.0.1, 6.1.0 Alpha, and later
- PySide6 6.10.2 should include these fixes
- White flickering on Windows during resize is a known OS-level behavior documented by Microsoft

**Documentation Link:**
- [Qt Bug Report - Flickering White Background](https://bugreports.qt.io/browse/QTBUG-89688)

### 7. Minimal Documented Pattern

**Source:** [Qt Forum - Collapsible Section](https://forum.qt.io/topic/127615/how-can-i-expand-and-collapse-part-of-my-form-with-qpropertyanimation)

**Pattern:**
```cpp
// Animate maximumHeight, not size
QPropertyAnimation *anim = new QPropertyAnimation(collapsibleWidget, "maximumHeight", this);
anim->setDuration(300);
anim->setStartValue(0);
anim->setEndValue(targetHeight);
anim->setEasingCurve(QEasingCurve::InOutQuart);
anim->start();
```

## Recommended Architecture for Our Case

### DO:

1. **Animate `maximumHeight` only** - Don't animate widget size or geometry directly
2. **Use `setUpdatesEnabled(false)`** - Disable updates on the window/widget hierarchy during animation, re-enable after
3. **Lock prompt widget size policy** - Set `QSizePolicy::Fixed` for prompt widget before animation, restore after
4. **Set layout size constraint** - Use `QLayout::SetNoConstraint` during animation to prevent layout interference
5. **Animate only the drawer container** - Don't animate the window geometry simultaneously if possible
6. **Use shorter durations** - 180ms is good; longer animations (500ms+) can show more flicker
7. **Set fixed height on prompt widget** - Lock `minimumHeight` and `maximumHeight` to current height before animation

### DON'T:

1. **Don't animate window geometry** - If possible, animate only the drawer height and let the window resize naturally
2. **Don't call `setMask()` during animation** - Set mask once before animation starts
3. **Don't change stylesheets during animation** - Stylesheet changes trigger full repaints
4. **Don't rely on layout auto-sizing** - Layouts will try to reposition widgets during animation
5. **Don't animate multiple conflicting properties** - Animating both drawer height and window geometry simultaneously can cause conflicts
6. **Don't use `WA_OpaquePaintEvent` with translucent backgrounds** - These are contradictory

## Concrete Implementation Checklist for PromptShellWindow

### Before Animation Starts (`_begin_drawer_transition`):

- [x] Save current layout size constraint
- [x] Set layout size constraint to `SetNoConstraint`
- [x] Save prompt widget size policy
- [x] Set prompt widget to `QSizePolicy::Fixed` (both horizontal and vertical)
- [x] Lock prompt widget `minimumHeight` and `maximumHeight` to current height
- [x] Save drawer frame size policy
- [x] Set drawer frame to `QSizePolicy::Fixed` (vertical)
- [ ] **NEW:** Call `setUpdatesEnabled(false)` on window/widget hierarchy
- [ ] **NEW:** Ensure `setMask()` is not called during animation (already done)

### During Animation:

- [x] Animate `drawer_frame.maximumHeight` only
- [x] Animate `middle_host.maximumHeight` 
- [x] Animate window `geometry` (consider removing this)
- [ ] **NEW:** Ensure no layout recalculation triggers
- [ ] **NEW:** Avoid any repaint triggers (no style changes, no mask changes)

### After Animation Completes (`_end_drawer_transition`):

- [x] Restore layout size constraint
- [x] Restore prompt widget size policy
- [x] Restore prompt widget min/max heights
- [x] Restore drawer frame size policy
- [ ] **NEW:** Call `setUpdatesEnabled(true)` to re-enable updates
- [ ] **NEW:** Force a single repaint with `update()` or `repaint()`

### Alternative Approach (Recommended):

Instead of animating window geometry, consider:

1. **Only animate drawer height** - Let the window naturally resize via layout
2. **Use `QTimer` to snap window position** - After animation completes, adjust window position to maintain bottom anchor
3. **Or use `resizeEvent` override** - Track bottom anchor and adjust window Y position when height changes

## Risky Anti-Patterns to Avoid

1. **Animating window geometry during layout animation** - Causes double-update conflicts
2. **Calling `setMask()` in `resizeEvent`** - Expensive and causes flicker
3. **Changing stylesheets during animation** - Triggers full widget repaint
4. **Relying on layout auto-sizing** - Layouts reposition widgets, conflicting with animations
5. **Not disabling updates during animation** - Allows intermediate repaints causing flicker
6. **Animating multiple properties simultaneously** - Can cause synchronization issues
7. **Using `WA_OpaquePaintEvent` with `WA_TranslucentBackground`** - Contradictory attributes
8. **Not locking size policies** - Layout can override animation values
9. **Long animation durations** - 500ms+ animations show more flicker artifacts
10. **Not restoring state after animation** - Leaves widget in inconsistent state

## Additional Recommendations

### For Windows DWM Compatibility:

1. **Test on Windows 10/11** - DWM behavior varies by version
2. **Consider shorter animation duration** - 150-200ms reduces visible flicker
3. **Use `QTimer::singleShot`** - Delay final geometry snap until after animation completes
4. **Monitor for Qt updates** - Ensure PySide6 6.10.2 includes Qt 6.0.1+ fixes

### Debugging Tips:

1. **Enable verbose debug logging** - Track geometry changes during animation
2. **Monitor `prompt_global_dy`** - Should remain 0-1 pixels if prompt is truly fixed
3. **Check layout constraint state** - Ensure `SetNoConstraint` is active during animation
4. **Verify updates are disabled** - Check `updatesEnabled()` returns false during animation

## References

- [QPropertyAnimation Class](https://doc.qt.io/qt-6/qpropertyanimation.html)
- [QWidget::setUpdatesEnabled](https://doc.qt.io/qt-6/qwidget.html#setUpdatesEnabled)
- [QLayout Class](https://doc.qt.io/qt-6/qlayout.html)
- [Qt Animation Framework](https://doc.qt.io/qt-6/animation-overview.html)
- [Qt Windows Issues](https://doc.qt.io/qt-6/windows-issues.html)
- [Qt Bug Report QTBUG-89688](https://bugreports.qt.io/browse/QTBUG-89688)
- [Qt Forum - Expand/Collapse Animation](https://forum.qt.io/topic/127615/how-can-i-expand-and-collapse-part-of-my-form-with-qpropertyanimation)
- [Qt Forum - Borderless Translucent Widget](https://forum.qt.io/topic/24274/solved-borderless-transculent-widget-updating-problem)
