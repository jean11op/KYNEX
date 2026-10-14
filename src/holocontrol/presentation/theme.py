"""Paleta y superficies compartidas; mantiene temas accesibles y foco visible."""


def stylesheet(theme, size=13):
    light = theme == 'Claro'
    contrast = theme == 'Alto contraste'
    bg, card, fg, muted, border, field = (
        ('#f0f4fa', '#ffffff', '#16283a', '#4f657c', '#cfdae6', '#f4f7fb')
        if light else ('#0b1019', '#151e2b', '#ecf3ff', '#a4b5ca', '#28384c', '#111b29')
    )
    if contrast:
        bg, card, fg, muted, border, field = '#000000', '#080808', '#ffffff', '#eeeeee', '#dddddd', '#111111'
    accent = '#0069b9' if light else '#86caff'
    selected = '#deedff' if light else '#1e3e5e'
    top = '#ffffff' if light else '#1a2738'
    if contrast:
        top = card
    return f'''
        QWidget {{ color: {fg}; font-family: "Segoe UI"; font-size: {size}px; }}
        QWidget#root, QWidget#page, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {bg}; }}
        QFrame#rail {{ background: {card}; border-right: 1px solid {border}; }}
        QFrame#panel {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {top},stop:1 {card}); border: 1px solid {border}; border-radius: 19px; }}
        QLabel {{ background: transparent; }}
        QLabel#brand {{ font-size: 33px; font-weight: 750; padding-left: 8px; }}
        QLabel#eyebrow {{ font-size: 10px; color: {muted}; font-weight: 600; letter-spacing: 1px; }}
        QLabel#heroTitle {{ font-size: {size + 19}px; font-weight: 650; letter-spacing: -1px; }}
        QLabel#heading {{ font-size: {size + 15}px; font-weight: 650; padding-top: 10px; }}
        QLabel#subheading {{ font-size: {size + 4}px; font-weight: 600; }}
        QLabel#cardTitle {{ font-size: {size + 1}px; font-weight: 600; }}
        QLabel#muted, QLabel#small {{ color: {muted}; font-size: {max(11, size - 1)}px; }}
        QLabel#metric {{ font-size: {size + 4}px; font-weight: 600; }}
        QLabel#tileCaption {{ font-size: {max(11, size - 2)}px; }}
        QLabel#accent {{ color: {accent}; font-weight: 600; }}
        QLabel#error {{ color: {'#a32130' if light else '#ffa8b7'}; }}
        QLabel#statusPill {{ color: {'#166855' if light else '#99dac5'}; background: {'#e2f4ee' if light else '#172c2c'}; border: 1px solid {'#b5ddcf' if light else '#2b4944'}; border-radius: 13px; padding: 6px 12px; font-size: 11px; }}
        QLabel#toast {{ color: {fg}; background: {card}; border: 1px solid {accent}; border-radius: 12px; padding: 15px 20px; }}
        QFrame#separator {{ background: {border}; }}
        QPushButton {{ background: {field}; border: 1px solid {border}; border-radius: 10px; padding: 7px 14px; font-weight: 500; }}
        QPushButton:focus, QComboBox:focus, QSpinBox:focus, QLineEdit:focus, QKeySequenceEdit:focus, QListWidget:focus {{ border: 2px solid {accent}; }}
        QPushButton#nav {{ background: transparent; border: 1px solid transparent; padding: 6px 10px; text-align: left; color: {muted}; }}
        QPushButton#nav:checked {{ background: {selected}; color: {fg}; border-color: {'#b9d3f1' if light else '#315675'}; }}
        QPushButton#nav:focus {{ border-color: {accent}; }}
        QPushButton#primary {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #398ee8,stop:1 #2466c6); color: #ffffff; border: 1px solid #5ea6ef; font-weight: 600; }}
        QPushButton#secondary {{ background: {selected}; color: {accent}; border-color: {'#bad4ef' if light else '#375875'}; }}
        QPushButton#link {{ background: transparent; color: {accent}; border-color: transparent; }}
        QPushButton#profileChip {{ background: {field}; padding: 5px 14px; }}
        QPushButton#chip {{ padding: 3px 8px; font-size: {max(11, size - 2)}px; }}
        QPushButton#chip:checked {{ background: {selected}; color: {accent}; border-color: {accent}; }}
        QPushButton#gesture {{ background: {field}; text-align: left; padding: 9px; font-size: {max(11, size - 1)}px; }}
        QPushButton:disabled, QPushButton#primary:disabled {{ background: {field}; color: {'#677a8c' if light else '#8494a8'}; border-color: {border}; }}
        QProgressBar {{ border: none; border-radius: 2px; background: {field}; }}
        QProgressBar::chunk {{ background: {accent}; border-radius: 2px; }}
        QSlider::groove:horizontal {{ height: 5px; background: {border}; border-radius: 2px; }}
        QSlider::sub-page:horizontal {{ background: {accent}; border-radius: 2px; }}
        QSlider::handle:horizontal {{ background: {accent}; border: 2px solid {card}; width: 16px; margin: -7px 0; border-radius: 9px; }}
        QSlider:focus {{ border: 1px solid {accent}; border-radius: 4px; }}
        QTabWidget::pane {{ border: none; }}
        QTabBar::tab {{ background: {field}; color: {muted}; padding: 8px 7px; font-size: {max(10, size - 3)}px; border-bottom: 2px solid transparent; }}
        QTabBar::tab:selected {{ color: {accent}; border-bottom: 2px solid {accent}; }}
        QLineEdit, QComboBox, QSpinBox, QKeySequenceEdit, QListWidget {{ background: {field}; border: 1px solid {border}; border-radius: 8px; padding: 8px; min-height: 24px; selection-background-color: {selected}; }}
        QComboBox::drop-down {{ border: none; width: 22px; }}
        QComboBox::down-arrow {{ image: url({{CHEVRON}}); width: 12px; height: 12px; }}
        QListWidget::item {{ padding: 18px; border-bottom: 1px solid {border}; }}
        QListWidget::item:selected {{ background: {selected}; color: {fg}; border-radius: 8px; }}
        QComboBox QAbstractItemView {{ background: {card}; selection-background-color: {selected}; color: {fg}; border: 1px solid {border}; }}
        QDialog, QMessageBox, QMenu {{ background: {card}; }}
        QMenu {{ border: 1px solid {border}; padding: 6px; }}
        QMenu::item {{ padding: 9px 18px; }}
        QMenu::item:selected {{ background: {selected}; border-radius: 6px; }}
        QCheckBox {{ spacing: 10px; padding: 4px 0; }}
        QCheckBox::indicator {{ width: 18px; height: 18px; border: 1px solid {muted}; border-radius: 5px; background: {field}; }}
        QCheckBox::indicator:checked {{ background: #2984d6; border-color: #73bbf5; image: url({{CHECK}}); }}
        QToolTip {{ background: {card}; color: {fg}; border: 1px solid {border}; padding: 8px; border-radius: 6px; }}
        QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
        QScrollBar::handle:vertical {{ background: {border}; border-radius: 4px; min-height: 32px; }}
        QScrollBar::handle:vertical:hover {{ background: {muted}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
    '''
