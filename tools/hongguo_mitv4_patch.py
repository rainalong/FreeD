#!/usr/bin/env python3
"""Experimental MiTV4-ANSM0 portrait HEVC MPV fix.

This intentionally changes only the MPV player flavor. Do not interpret an
1088-row decoder buffer as evidence that the original frame was 1088 rows.
"""
from pathlib import Path

root = Path.cwd()
src = root / "android/app/src/mpv/java/rocks/aston/hongguotv"
bridge = src / "MpvPlayerBridge.java"
fallback = src / "MpvFallbackPolicy.java"
geometry = src / "MpvPortraitGeometryPolicy.java"

def patch(path, before, after):
    data = path.read_text(encoding="utf-8")
    if data.count(before) != 1:
        raise RuntimeError(f"Unexpected upstream source layout: {path.name} count={data.count(before)}")
    path.write_text(data.replace(before, after, 1), encoding="utf-8")

geometry.write_text("""package rocks.aston.hongguotv;

/** Recognize a portrait HEVC frame whose height was replaced by a decoder buffer height. */
final class MpvPortraitGeometryPolicy {
    private MpvPortraitGeometryPolicy() {}
    static boolean broken(int sourceW, int sourceH, int decodedW, int decodedH,
                          boolean hevc, boolean hardware) {
        return hevc && hardware && sourceW >= 320 && sourceH >= 1184
            && sourceH > sourceW * 1.2
            && decodedW > 0 && decodedH >= 1000 && decodedH <= 1088
            && sourceH - decodedH >= 96
            && Math.abs(sourceW - decodedW) <= 16;
    }
}
""", encoding="utf-8")

patch(bridge,
    '        target.output.configured = Boolean.TRUE.equals(player.getPropertyBoolean("vo-configured"));\n        Boolean coreIdle',
    '        target.output.configured = Boolean.TRUE.equals(player.getPropertyBoolean("vo-configured"));\n'
    '        if (target.output.loaded && portraitOutputBroken(target)) {\n'
    '            retrySoftware(target, "portrait_geometry", false);\n'
    '            return;\n'
    '        }\n'
    '        Boolean coreIdle')

patch(bridge,
    '    private static String activeHwdec(Session target) {\n'
    '        return target.softwareFallback ? "no" : target.mode.hwdec;\n'
    '    }\n'
    '    private static boolean isHardwareDecoder',
    '    private static String activeHwdec(Session target) {\n'
    '        if (target.softwareFallback) return "no";\n'
    '        if (target.mode == MpvDecodeMode.AUTOMATIC &&\n'
    '                "MiTV4-ANSM0".equals(android.os.Build.MODEL)) return "mediacodec";\n'
    '        return target.mode.hwdec;\n'
    '    }\n'
    '    private static int nonzero(Integer n) { return n == null || n < 1 ? 0 : n; }\n'
    '    private boolean portraitOutputBroken(Session target) {\n'
    '        MPVLib active = target.player;\n'
    '        if (active == null || target.mode != MpvDecodeMode.AUTOMATIC ||\n'
    '                target.softwareFallback || !"MiTV4-ANSM0".equals(android.os.Build.MODEL))\n'
    '            return false;\n'
    '        int sourceW = nonzero(active.getPropertyInt("current-tracks/video/demux-w"));\n'
    '        int sourceH = nonzero(active.getPropertyInt("current-tracks/video/demux-h"));\n'
    '        int decodedW = nonzero(active.getPropertyInt("video-dec-params/w"));\n'
    '        int decodedH = nonzero(active.getPropertyInt("video-dec-params/h"));\n'
    '        return MpvPortraitGeometryPolicy.broken(sourceW, sourceH, decodedW, decodedH,\n'
    '            "hevc".equalsIgnoreCase(property(active, "video-codec")), isHardwareDecoder(active));\n'
    '    }\n'
    '    private static boolean isHardwareDecoder')

patch(fallback,
    '        return "known_broken_profile".equals(reason)\n'
    '            || "green_frame".equals(reason)',
    '        return "known_broken_profile".equals(reason)\n'
    '            || "portrait_geometry".equals(reason)\n'
    '            || "green_frame".equals(reason)')

print("Patched MPV HEVC decode path and portrait geometry guard.")
