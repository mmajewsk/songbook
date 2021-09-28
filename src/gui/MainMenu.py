from PySide6.QtWidgets import (QWidget, QVBoxLayout, QPushButton,
                                QLabel)
from PySide6.QtGui import QPixmap

from src.gui.SongEditor import ScrollableSongEditor

from src.gui.CategoryEditor import NewCategory

from src.gui.SongList import ScrollAndSearchSongList

from src.tools.openDefault import open_with_default_app

from src import TeXcompile, songbookTeXmaker

import os

class MainMenu(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Songbook Maker')

        label = QLabel()
        image = QPixmap("logo")
        if image:            
            label.setPixmap(image)
        else:
            label.setText("Songbook Maker\n<Warning: Logo.png is missing>")
            
        categoryButton = QPushButton('New Category', self)
        categoryButton.clicked.connect(self.addCategoryField)
        
        songButton = QPushButton('Song Editor', self)
        songButton.clicked.connect(self.addSongField)

        listButton = QPushButton('Songs List', self)
        listButton.clicked.connect(self.listSongsField)

        compileButton = QPushButton('Create PDF', self)
        compileButton.clicked.connect(self.generateAndCompileTex)

        layout = QVBoxLayout()
        layout.addWidget(label)
        layout.addWidget(categoryButton)
        layout.addWidget(songButton)
        layout.addWidget(listButton)
        layout.addWidget(compileButton)
        self.setLayout(layout)
        self.show()

    def generateAndCompileTex(self):
        songbookTexFile = songbookTeXmaker.main()
        songbookPdfFile = TeXcompile.main()
        open_with_default_app(os.path.join(os.getcwd(), songbookPdfFile))



    def listSongsField(self):
        self.songList = ScrollAndSearchSongList()
    def addSongField(self):
        self.currentSong = ScrollableSongEditor()
    def addCategoryField(self):
        self.currentCat = NewCategory()