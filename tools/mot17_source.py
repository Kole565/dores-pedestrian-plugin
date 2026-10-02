import configparser
from pathlib import Path

import cv2


class Mot17Sequence:
    """Замена cv2.VideoCapture для MOT17-последовательности (папка img1/*.jpg)."""

    def __init__(self, seq_dir: str):
        self.seq_dir = Path(seq_dir)
        cp = configparser.ConfigParser()
        cp.read(self.seq_dir / "seqinfo.ini")
        s = cp["Sequence"]

        self.im_dir = self.seq_dir / s["imDir"]
        self.ext = s["imExt"]
        self.fps = float(s["frameRate"])
        self.width = int(s["imWidth"])
        self.height = int(s["imHeight"])

        self.frames = sorted(self.im_dir.glob(f"*{self.ext}"))
        self._idx = 0

    def isOpened(self) -> bool:
        return len(self.frames) > 0

    def read(self):
        if self._idx >= len(self.frames):
            return False, None
        img = cv2.imread(str(self.frames[self._idx]))
        self._idx += 1
        return (img is not None), img

    def get(self, prop: int) -> float:
        if prop == cv2.CAP_PROP_FRAME_WIDTH:  return float(self.width)
        if prop == cv2.CAP_PROP_FRAME_HEIGHT: return float(self.height)
        if prop == cv2.CAP_PROP_FPS:          return self.fps
        if prop == cv2.CAP_PROP_FRAME_COUNT:  return float(len(self.frames))
        return 0.0

    def release(self):
        self.frames = []
        self._idx = 0
