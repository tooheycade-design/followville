# patch bootstrap preview render for Blender 5 media_type
import re
p = "/Users/cadetoohey/Documents/neighborhood/_setup_bootstrap.py"
s = open(p).read()
old = 'sc.render.image_settings.file_format = "PNG"'
new = ('try:\n'
       '    sc.render.image_settings.media_type = "IMAGE"\n'
       'except Exception:\n'
       '    pass\n'
       'sc.render.image_settings.file_format = "PNG"')
if "media_type" not in s:
    s = s.replace(old, new)
    open(p, "w").write(s)
    print("patched")
else:
    print("already patched")
