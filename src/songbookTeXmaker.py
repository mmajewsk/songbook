import os
import json
import re

from src.tools.plAlphabetSort import plSortKey
import asyncio
import aiofiles
    
from src import headerconfig as headerconfig

from src.tools.chordShift import shiftChords
from src.tools.codings import enUTF8, deUTF8

from src.obj.Config import config


def isSongCategoryDir(dirname):
    return os.path.isdir(os.path.join(config.dataFolder, dirname)) and not (dirname.startswith((".", "_")))

async def gatherAllCategories(sem):
    tasks = [gatherSongs(os.path.join(config.dataFolder, dirname), sem) for dirname in os.listdir(config.dataFolder) if isSongCategoryDir(dirname)]
    categories = await asyncio.gather(*tasks)
    return categories

async def gatherSongs(dirpath, sem):
    tasks = [semaphoredLoadSong(dirpath, filename, sem) for filename in os.listdir(dirpath) if filename.endswith(".sng")]
    songs = await asyncio.gather(*tasks)
    return songs
    
async def semaphoredLoadSong(dirpath, filename, sem):
    async with sem:
        return await Song.load(os.path.join(dirpath, filename))

class CategoryDict(dict):
    def __missing__(self, key):
        res = self[key] = Category(key)
        return res

class Category:
    def __init__(self, name):
        self.songs = {}
        self.name = name
    def setCatMapping(self, catsDict):
        self.catMap = catsDict
    @property
    def tex(self):
        try: 
            name = self.catMap[self.name]
        except (KeyError, AttributeError):
            name = self.name
        catStr = ""
        if config.canvas.sides == "twoside":
            catStr += "\\cleardoublepage\n"
        catStr += f"\\chapter*{{\centering {name}}}\n" + \
        f"\\addcontentsline{{toc}}{{chapter}}{{{name}}}\n" + \
        f"{{\\centering \\includegraphics[width=\\textwidth,height=0.75\\textheight,keepaspectratio]{{{self.name}}} \\par}}\n" 
        catStr += "\\newpage\n"
        return catStr

class Song:
    @staticmethod
    async def load(filepath):
        async with aiofiles.open(filepath, "r") as songFile:
            song = Song(await songFile.read())
        return song

    def __init__(self, songJSON):
        self.dict = json.loads(songJSON)
        self.title = self.dict['title']
        self.category = self.dict['category']
    @property
    def tex(self):
        songStr = f"\\section*{{{self.title}}}\n\\addcontentsline{{toc}}{{section}}{{{self.title}}}\n\\columnratio{{0.75,0.25}}\n\\rmfamily"
        try:
            author = self.dict['author']
            songStr += f"\\begin{{flushright}}\n{author}\n\\end{{flushright}}"
        except KeyError:
            pass
        try:
            capo = self.dict['capo']
            songStr += f"\\begin{{flushright}}\n{capo}\n\\end{{flushright}}"
        except KeyError:
            pass
        songStr += "\\begin{paracol}{2}\n"
        for section in self.dict['sections']:
            songStr += self.convertSection(section)
        songStr += "\\end{paracol}\n"
        songStr += "\\newpage\n"
        return songStr

    def superscriptSpecialChars(self, text):
        specialChars = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "+", "-", "*", "sus", "add", "/"]
        chDict = {ch:f"\\textsuperscript{{{ch}}}" for ch in specialChars}
        pattern = re.compile('|'.join(sorted([re.escape(key) for key in chDict.keys()], key=len, reverse=True)))
        result = pattern.sub(lambda x: chDict[x.group()], text)
        return result
        
    def convertSection(self, section):
        chordShift = config.chordShift
        lyrics, l1 = self.convertLineBreaks(section['lyrics'])
        if section['chords']:
            chords, l2 = self.convertLineBreaks(shiftChords(section['chords'], chordShift).replace("\\", "\\textbackslash "))
        else:
            chords, l2 = "", 0
        songStr = f"\n\\ensurevspace{{{max(l1, l2)+2}\\baselineskip}}\n"
        songStr += "\\begin{leftcolumn*}\n"
        if section['chorus']:
            lyrics = self.chorusWrapper(lyrics)
        songStr += lyrics
        songStr += "\\end{leftcolumn*}\n"
        if chords:
            songStr += "\\begin{rightcolumn}\n"
            songStr += "\\begin{bfseries}\n"
            songStr += "\n\\ttfamily\n"
            songStr += self.superscriptSpecialChars(chords)
            songStr += "\\end{bfseries}\n"
            songStr += "\\end{rightcolumn}\n"
            songStr += "\n\\rmfamily\n"
        return songStr

    def chorusWrapper(self, text):
        wrapped_text = "\\begin{chorus}\n" + text + "\\end{chorus}\n"
        return wrapped_text

    def convertLineBreaks(self, text):
        converted_text = ""
        lines = text.splitlines()
        for line in lines:
            if line:
                converted_text += line + "\\\\\n" 
            else:
                converted_text += "\\vspace{\\baselineskip}\n"
        return converted_text, len(lines)

async def copyHeader(headerFilename, songbookFilename):
    async with aiofiles.open(songbookFilename, "wb") as songbookFile:
        async with aiofiles.open(headerFilename, "rb") as headerFile:
            await songbookFile.write(await headerFile.read())

def makeSongbookDict(songs):
    songbookDict = CategoryDict()
    for category in songs:
        for song in category:
            songbookDict[song.category].songs[song.title] = song
    return songbookDict

async def getCategoriesConfig(configFilepath, songbookDict):
    try:
        async with aiofiles.open(configFilepath, "rb") as configFile:
            cats_dict = json.loads(deUTF8(await configFile.read()))
    except FileNotFoundError:
        print("mapping not found")
        cats_dict = {cat:cat for cat in sorted(songbookDict.keys(), key=plSortKey)}
    return cats_dict

async def processCategory(cat, songbookFile, ignoredSongs = None):
    keys = cat.songs.keys()
    ignoredCount = 0
    for songKey in sorted(keys, key=plSortKey):
        song = cat.songs[songKey]
        if (cat.name, song.title) not in ignoredSongs:
            print("\t" + song.title)
            await songbookFile.write(enUTF8(song.tex))
        else:
            ignoredCount += 1
    return len(keys) - ignoredCount

async def processSingleSong(song, songbookFile):
    print("\t" + song.title)
    await songbookFile.write(enUTF8(song.tex))
    return 1

def main():
    return asyncio.run(_asyncMain())

async def _asyncMain():
    headerconfig.main()
    
    texOutFile = f"{config.outputFile}.tex"

    await copyHeader(os.path.join(config.dataFolder, config.latexHeaderFile), texOutFile)
    

    sem = asyncio.Semaphore(100)

    gatheredSongs = await gatherAllCategories(sem)

    songbookDict = makeSongbookDict(gatheredSongs)

    cats = await getCategoriesConfig(os.path.join(config.dataFolder, config.categoriesFile), songbookDict)

    for cat in songbookDict.values():
        cat.setCatMapping(cats)

    songCount = 0
    print("Title songs")


    async with aiofiles.open(texOutFile, "ab") as songbookFile:

        titleSongs = [("Turystyczne", "Hawiarska Koliba")]
        for titleSong in titleSongs:
            songCount += await processSingleSong(songbookDict[titleSong[0]].songs[titleSong[1]], songbookFile)
        
        await songbookFile.write(enUTF8("\n\t\\chapter*{Spis treści}\n\\begin{multicols}{2}\n\\tableofcontents\n\\end{multicols}\n"))

        for cat in cats.keys():
            if cat != "Title":
                print(cat)
                await songbookFile.write(enUTF8(songbookDict[cat].tex))
                songCount += await processCategory(songbookDict[cat], songbookFile, titleSongs)

        await songbookFile.write(enUTF8(f"\\IfFileExists{{{config.outputFile}_list.toc}}{{\n\t\\chapter*{{Spis treści}}\n\\begin{{multicols}}{{2}}\n\t\\input{{{config.outputFile}_list.toc}}\n\\end{{multicols}}\n}}{{}}\n"))
        await songbookFile.write(enUTF8("\\end{document}"))
    print(f"Total number of songs: {songCount}")
    return texOutFile
    
if __name__=="__main__":
    main()
