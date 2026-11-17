#!/usr/bin/env python3
"""MiTV4-ANSM0 portrait HEVC GPU aspect experiment, no CPU fallback for dimensions.

MediaCodec may truly crop a 1920-row picture to 1088 rows. This experimental
patch only overrides MPV's displayed aspect ratio: it cannot recover data
missing from the hardware output. Other MPV fallback triggers stay enabled.
"""
from pathlib import Path

src = Path.cwd() / "android/app/src/mpv/java/rocks/aston/hongguotv"
bridge = src / "MpvPlayerBridge.java"
geometry = src / "MpvPortraitGeometryPolicy.java"

def patch(path, before, after):
    data = path.read_text(encoding="utf-8")
    if data.count(before) != 1:
        raise RuntimeError(f"Unexpected upstream source: {path.name} count={data.count(before)}")
    path.write_text(data.replace(before, after, 1), encoding="utf-8")

geometry.write_text("""package rocks.aston.hongguotv;

/** A narrow test condition for legacy Amlogic HEVC portrait dimensions. */
final class MpvPortraitGeometryPolicy {
    private MpvPortraitGeometryPolicy() {}
    static boolean broken(int sw, int sh, int dw, int dh, boolean hevc, boolean hardware) {
        return hevc && hardware && sw >= 320 && sh >= 1184
            && sh > sw * 1.2 && dw > 0
            && dh >= 1000 && dh <= 1088
            && sh - dh >= 96
            && Math.abs(sw - dw) <= 16;
    }
}
""", encoding="utf-8")

patch(bridge,
    '        boolean softwareFallback;\n',
    '        boolean softwareFallback, portraitAspectFixed;\n')

patch(bridge,
    '        target.output.configured = Boolean.TRUE.equals(player.getPropertyBoolean("vo-configured"));\n        Boolean coreIdle',
    '        target.output.configured = Boolean.TRUE.equals(player.getPropertyBoolean("vo-configured"));\n'
    '        if (target.output.loaded && portraitOutputBroken(target) && !target.portraitAspectFixed) {\n'
    '            int sw = nonzero(player.getPropertyInt("current-tracks/video/demux-w"));\n'
    '            int sh = nonzero(player.getPropertyInt("current-tracks/video/demux-h"));\n'
    '            if (sw > 0 && sh > 0) {\n'
    '                try {\n'
    '                    player.setPropertyString("video-aspect-override", sw + ":" + sh);\n'
    '                    target.portraitAspectFixed = true;\n'
    '                } catch (RuntimeException ignored) { /* retain hardware and diagnostic */ }\n'
    '            }\n'
    '        }\n'
    '        Boolean coreIdle')

patch(bridge,
    '            target.player.setPropertyString("hwdec", activeHwdec(target));\n'
    '            target.player.setPropertyString("force-window", "yes");',
    '            target.player.setPropertyString("hwdec", activeHwdec(target));\n'
    '            target.player.setPropertyString("video-aspect-override", "no");\n'
    '            target.player.setPropertyString("force-window", "yes");')

patch(bridge,
    '            active.setPropertyString("hwdec", activeHwdec(target));\n'
    '            target.pendingSeek = target.position > 0;',
    '            active.setPropertyString("hwdec", activeHwdec(target));\n'
    '            active.setPropertyString("video-aspect-override", "no");\n'
    '            target.pendingSeek = target.position > 0;')

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
    '        int sw = nonzero(active.getPropertyInt("current-tracks/video/demux-w"));\n'
    '        int sh = nonzero(active.getPropertyInt("current-tracks/video/demux-h"));\n'
    '        int dw = nonzero(active.getPropertyInt("video-dec-params/w"));\n'
    '        int dh = nonzero(active.getPropertyInt("video-dec-params/h"));\n'
    '        return MpvPortraitGeometryPolicy.broken(sw, sh, dw, dh,\n'
    '            "hevc".equalsIgnoreCase(property(active, "video-codec")), isHardwareDecoder(active));\n'
    '    }\n'
    '    private static boolean isHardwareDecoder')

patch(bridge,
    '                .put("width", target.output.width).put("height", target.output.height).put("speed", speed)',
    '                .put("width", target.output.width).put("height", target.output.height).put("speed", speed)\n'
    '                .put("portrait_aspect_fixed", target.portraitAspectFixed)')

patch(bridge,
    '                fields.put("video_decoder", target.decoder).put("hwdec_current", property(player, "hwdec-current"));',
    '                fields.put("video_decoder", target.decoder).put("hwdec_current", property(player, "hwdec-current"));\n'
    '                fields.put("portrait_source_width", nonzero(player.getPropertyInt("current-tracks/video/demux-w")))\n'
    '                    .put("portrait_source_height", nonzero(player.getPropertyInt("current-tracks/video/demux-h")))\n'
    '                    .put("portrait_ratio_override", property(player, "video-aspect-override"));')

print("Patched MiTV4 hardware HEVC portrait aspect experiment (NO geometry CPU fallback).")
