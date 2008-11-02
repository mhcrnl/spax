
import os
import string
import sys
import wx
import fnmatch
import re
from wax.treeview import TreeView
from wax.imagelist import ImageList
from wax import Menu

from spax.prefs import prefs

PREF_TREE = 'tree'
PREF_TREE_ROOT = 'root'

class ContextMenu(Menu):
    def __init__(self, *args, **kwargs):
        super(ContextMenu, self).__init__(*args, **kwargs)

        self.Append('&Reset root directory', self.parent.OnResetRoot)
        self.Append('&Set directory as root', self.parent.OnSetRoot)

class ShowAllFileTreeView(TreeView):
    #add double-click event to expand nodes
    __events__ = TreeView.__events__
    __events__.update({
        'DoubleClick': wx.EVT_LEFT_DCLICK,
        'RightClick': wx.EVT_RIGHT_DOWN,
    })

    def __init__(self, parent, rootdir=None, exclude=None):
        TreeView.__init__(self, parent)
        self.rootdir = prefs.get(PREF_TREE, PREF_TREE_ROOT, '/')
        exclude = exclude or []
        self.exclude = re.compile(r'|'.join(["(%s)" % fnmatch.translate(g) for g in exclude]))

        imagelist = ImageList(16, 16)
        imagelist.Add(wx.ArtProvider_GetBitmap(wx.ART_FOLDER, wx.ART_OTHER, (16,16)), 'folder')
        imagelist.Add(wx.ArtProvider_GetBitmap(wx.ART_FILE_OPEN, wx.ART_OTHER, (16,16)), 'folder_open')
        imagelist.Add(wx.ArtProvider_GetBitmap(wx.ART_NORMAL_FILE, wx.ART_OTHER, (16,16)), 'file')
        self.SetImageList(imagelist)
        self.MakeRoot()

    def SetImages(self, node, isdir):
        if isdir:
            self.SetItemImage(node, self._imagelist['folder'], expanded=0)
            self.SetItemImage(node, self._imagelist['folder_open'], expanded=1)
        else:
            self.SetItemImage(node, self._imagelist['file'])

    def MakeRoot(self):
        """ Add the toplevel nodes to the tree.  For Unix, this is simple:
            get the root directory, and look at the subdirectories there.
            For Windows, however, we have to get the available drive letters. """
        self.Clear()
        text = os.path.split(self.rootdir[-1:] == '/' and self.rootdir[:-1] or self.rootdir)[1]
        self.root = self.AddRoot(self.rootdir)
        self.SetItemPyData(self.root, self.rootdir)
        self.SetImages(self.root, True)

        # get a list of tuples (short, long)
        if sys.platform == 'win32':
            a = self._win32_get_drive_letters()
            children = [(d, d, True) for d in a]
            self.AddChildren(self.root, children)
        else:
            self.SetItemHasChildren(self.root, True)
        self.Expand(self.root)

    def _win32_get_drive_letters(self):
        drives = []
        try:
            # check if win32all is available
            import win32api
        except ImportError:
            # if not, use os.path.exists to determine if drives exist
            # however, this may bring up an error dialog if there is no disk
            # in A:\
            for letter in string.uppercase:
                drive = letter + ":\\"
                if os.path.exists(drive):
                    drives.append(drive)
        else:
            drives = win32api.GetLogicalDriveStrings()
            drives = filter(None, string.splitfields(drives, "\000"))

        return drives

    def AddChildren(self, node, children):
        for short, long, isdir in children:
            child = self.AppendItem(node, short)
            self.SetPyData(child, long)
            self.SetImages(child, isdir)
            try:
                hasChildren = isdir and bool(os.listdir(long))
                if hasChildren:
                    self.SetItemHasChildren(child, hasChildren)
            except os.error:
                #most likely permission denied, thats ok.
                pass

    def OnRightClick(self, event):
        pos = event.GetPosition()
        item, where = self.HitTest(pos)
        if where & wx.TREE_HITTEST_NOWHERE:
            return
        self.SelectItem(item)

        filepath = self.GetItemData(item).GetData()
        if not os.path.isdir(filepath):
            return

        d = self.GetItemData(item).GetData()
        if (d == '/'):
            return
        else:
            menu = ContextMenu(self)

        self.selected = item

        self.PopupMenu(menu, event.GetPosition())
        menu.Destroy()

    def OnSetRoot(self, event):
        self.SetRoot(self.GetItemData(self.selected).GetData())

    def OnResetRoot(self, event):
        self.SetRoot('/')
        
    def SetRoot(self, path):
        self.rootdir = path
        prefs.set(PREF_TREE, PREF_TREE_ROOT, path)
        self.MakeRoot()

    def OnDoubleClick(self, event):
        pos = event.GetPosition()
        item, where = self.HitTest(pos)
        if where & wx.TREE_HITTEST_NOWHERE:
            return
        filepath = self.GetItemData(item).GetData()
        if os.path.isdir(filepath):
            self.Toggle(item)
        else:
            self.SelectItem(item)
            self.Parent.Parent.openFile(filepath)

    def OnItemExpanding(self, event):
        node = event.GetItem()
        nodes = self.GetChildNodes(node)
        try:
            nodes.next()
        except StopIteration:
            path = self.GetPyData(node)
            files = [(f, os.path.join(path, f), os.path.isdir(os.path.join(path, f))) for f in os.listdir(path) if not self.exclude.match(f)]
            children = sorted(files, key=lambda x:(-x[2], x[0]))
            self.AddChildren(node, children)
        self.Refresh()
