from sms_bin_editor.scene import SMSScene
scene = SMSScene.from_bytes(open("scene.bin", "rb"))
with open("scene_layout.log", "w", encoding="shift-jis") as f:
    scene.dump(f)