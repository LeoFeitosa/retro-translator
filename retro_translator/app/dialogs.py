"""The file and folder pickers: native on Windows (the executable's Python has no tkinter), tkinter elsewhere."""
import os

from retro_translator import consoles

def _open_windows():
    """Native open-file dialog (the executable's Python has no tkinter)."""
    import ctypes
    from ctypes import wintypes

    class OFN(ctypes.Structure):
        _fields_ = [("lStructSize", wintypes.DWORD), ("hwndOwner", wintypes.HWND), ("hInstance", wintypes.HINSTANCE),
                    ("lpstrFilter", wintypes.LPCWSTR), ("lpstrCustomFilter", wintypes.LPWSTR),
                    ("nMaxCustFilter", wintypes.DWORD), ("nFilterIndex", wintypes.DWORD), ("lpstrFile", wintypes.LPWSTR),
                    ("nMaxFile", wintypes.DWORD), ("lpstrFileTitle", wintypes.LPWSTR), ("nMaxFileTitle", wintypes.DWORD),
                    ("lpstrInitialDir", wintypes.LPCWSTR), ("lpstrTitle", wintypes.LPCWSTR), ("Flags", wintypes.DWORD),
                    ("nFileOffset", wintypes.WORD), ("nFileExtension", wintypes.WORD), ("lpstrDefExt", wintypes.LPCWSTR),
                    ("lCustData", wintypes.LPARAM), ("lpfnHook", ctypes.c_void_p), ("lpTemplateName", wintypes.LPCWSTR),
                    ("pvReserved", ctypes.c_void_p), ("dwReserved", wintypes.DWORD), ("FlagsEx", wintypes.DWORD)]
    buf = ctypes.create_unicode_buffer(1024)
    ofn = OFN(lStructSize=ctypes.sizeof(OFN), lpstrFilter="Game\0" + ";".join("*" + e for e in consoles.extensions()) + "\0All files\0*.*\0\0",
              lpstrFile=ctypes.cast(buf, wintypes.LPWSTR), nMaxFile=1024, lpstrTitle="Choose a Mega Drive ROM",
              Flags=0x1000 | 0x800)
    return buf.value if ctypes.windll.comdlg32.GetOpenFileNameW(ctypes.byref(ofn)) else None


def _folder_windows(title_):
    """Native folder dialog (Windows)."""
    import ctypes
    from ctypes import wintypes

    class BI(ctypes.Structure):
        _fields_ = [("hwndOwner", wintypes.HWND), ("pidlRoot", ctypes.c_void_p), ("pszDisplayName", wintypes.LPWSTR),
                    ("lpszTitle", wintypes.LPCWSTR), ("ulFlags", wintypes.UINT), ("lpfn", ctypes.c_void_p),
                    ("lParam", wintypes.LPARAM), ("iImage", ctypes.c_int)]
    ctypes.windll.ole32.CoInitialize(None)
    name_ = ctypes.create_unicode_buffer(260)
    shell = ctypes.windll.shell32
    shell.SHBrowseForFolderW.restype = ctypes.c_void_p
    pidl = shell.SHBrowseForFolderW(ctypes.byref(BI(None, None, ctypes.cast(name_, wintypes.LPWSTR), title_, 0x41,
                                                    None, 0, 0)))
    if not pidl:
        return None
    path_ = ctypes.create_unicode_buffer(1024)
    shell.SHGetPathFromIDListW(ctypes.c_void_p(pidl), path_)
    ctypes.windll.ole32.CoTaskMemFree(ctypes.c_void_p(pidl))
    return path_.value or None


def pick_rom():
    """The native open dialog; None when cancelled."""
    if os.name == "nt":
        return _open_windows()
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    rom = filedialog.askopenfilename(title="Choose a game", filetypes=[("Game", " ".join("*" + e for e in consoles.extensions())),
                                                                               ("All", "*")])
    root.destroy()
    return rom or None


def pick_folder(title_):
    if os.name == "nt":
        return _folder_windows(title_)
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    folder = filedialog.askdirectory(title=title_)
    root.destroy()
    return folder or None
