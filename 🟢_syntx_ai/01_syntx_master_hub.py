#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🟢 Syntx AI Master Hub -> Redirect Wrapper to 01_syntx_chat.py
تم تغيير اسم السكربت رسمياً إلى 01_syntx_chat.py بناءً على توجيه البروفيسور زيزو.
"""
import sys
import os

if __name__ == "__main__":
    chat_script = os.path.join(os.path.dirname(__file__), "01_syntx_chat.py")
    # تمرير كافة المعاملات لـ 01_syntx_chat.py
    import subprocess
    sys.exit(subprocess.run([sys.executable, chat_script] + sys.argv[1:]).returncode)
