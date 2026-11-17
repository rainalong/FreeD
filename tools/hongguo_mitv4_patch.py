#!/usr/bin/env python3
"""MiTV4 V4: hard decode retention plus geometry test, with zero silent CPU fallback.

Research-build guardrails:
* use the previously working MediaCodec COPY decoder instead of MediaCodec direct;
* do not silently switch MiTV4 to CPU decode through application heuristics;
* narrowly override the aspect ratio only for observed 720/1080x1088 HEVC;
* surface the current decoder and override in diagnostics.
"""
from pathlib import Path

src = Path.cwd() / "android/app/src/mpv/java/rocks/aston/hongguotv"
bridge = src / "MpvPlayerBridge.java"

def patch(before, after):
    data = bridge.read_text(encoding="utf-8")
    if data.count(before) != 1:
        raise RuntimeError("Unexpected upstream MpvPlayerBridge: " + repr(before[:75]))
    bridge.write_text(data.replace(before, after, 1), encoding="utf-8")

patch(
    '        boolean softwareFallback;\n',
    '        boolean softwareFallback, portraitAspectFixed;\n'
    '        String portraitAspectNote = "not_checked";\n'
)

# Do not poison the old automatic decoder choice with mediacodec(non-copy).
patch(
    '        return target.softwareFallback ? "no" : target.mode.hwdec;\n',
    '        if (target.softwareFallback) return "no";\n'
    '        if (target.mode == MpvDecodeMode.AUTOMATIC && isMiTV4()) return "mediacodec-copy";\n'
    '        return target.mode.hwdec;\n'
)

patch(
    '    private static boolean isHardwareDecoder(MPVLib active) {',
    '    private static boolean isMiTV4() {\n'
    '        return "MiTV4-ANSM0".equals(android.os.Build.MODEL);\n'
    '    }\n'
    '    private static int positive(Integer value) {\n'
    '        return value == null || value <= 0 ? 0 : value;\n'
    '    }\n'
    '    /** Test display aspect only; never claim to restore cropped HEVC samples. */\n'
    '    private void maybeApplyPortraitAspect(Session target) {\n'
    '        if (!isMiTV4() || target == null || target.player == null\n'
    '                || target.mode != MpvDecodeMode.AUTOMATIC || target.softwareFallback\n'
    '                || target.portraitAspectFixed) return;\n'
    '        MPVLib active = target.player;\n'
    '        if (!isHardwareDecoder(active)) {\n'
    '            target.portraitAspectNote = "not_hardware";\n'
    '            return;\n'
    '        }\n'
    '        if (!"hevc".equalsIgnoreCase(property(active, "video-codec"))) {\n'
    '            target.portraitAspectNote = "not_hevc";\n'
    '            return;\n'
    '        }\n'
    '        int w = positive(active.getPropertyInt("video-dec-params/w"));\n'
    '        int h = positive(active.getPropertyInt("video-dec-params/h"));\n'
    '        if (w == 0 || h == 0) {\n'
    '            w = positive(active.getPropertyInt("dwidth"));\n'
    '            h = positive(active.getPropertyInt("dheight"));\n'
    '        }\n'
    '        if (!((w == 720 || w == 1080) && h == 1088)) {\n'
    '            target.portraitAspectNote = "dimensions_" + w + "x" + h;\n'
    '            return;\n'
    '        }\n'
    '        int sw = positive(active.getPropertyInt("current-tracks/video/demux-w"));\n'
    '        int sh = positive(active.getPropertyInt("current-tracks/video/demux-h"));\n'
    '        // If the source format cannot be queried, use only the confirmed 9:16\n'
    '        // portrait variants. Do not apply this to other shapes or devices.\n'
    '        String aspect = sw == w && sh > sw && sh <= 4096\n'
    '            ? sw + ":" + sh : "9:16";\n'
    '        try {\n'
    '            active.setPropertyString("video-aspect-override", aspect);\n'
    '            target.portraitAspectFixed = true;\n'
    '            target.portraitAspectNote = "set_" + aspect;\n'
    '        } catch (RuntimeException e) {\n'
    '            target.portraitAspectNote = "override_rejected";\n'
    '        }\n'
    '    }\n'
    '    private static boolean isHardwareDecoder(MPVLib active) {'
)

# Guard every software fallback path, not only 'portrait_geometry'.
# Memory branches are instead gated with !isMiTV4() below.
# Important: without bypassing the memory branches, they return before rendering.
patch(
    '                                    && isHardwareDecoder(active) && decodeMemory.isBroken(loadedProfile)) {',
    '                                    && !isMiTV4() && isHardwareDecoder(active) && decodeMemory.isBroken(loadedProfile)) {'
)
patch(
    '                && isHardwareDecoder(player) && decodeMemory.isBroken(currentDecodeProfile(target))) {',
    '                && !isMiTV4() && isHardwareDecoder(player) && decodeMemory.isBroken(currentDecodeProfile(target))) {'
)
patch(
    '    private void retrySoftware(Session target, String reason, boolean rememberProfile) {\n'
    '        if (!current(target) || !MpvFallbackPolicy.canRetryInSoftware',
    '    private void retrySoftware(Session target, String reason, boolean rememberProfile) {\n'
    '        if (isMiTV4()) {\n'
    '            target.fallbackReason = "suppressed_" + reason;\n'
    '            updateDiagnostic(target, null);\n'
    '            return;\n'
    '        }\n'
    '        if (!current(target) || !MpvFallbackPolicy.canRetryInSoftware'
)
patch(
    '        if (MpvFallbackPolicy.canRetryInSoftware(target.mode, target.softwareFallback,\n'
    '                isHardwareDecoder(target.player), kind, target.output.videoDecodeError())) {',
    '        if (!isMiTV4() && MpvFallbackPolicy.canRetryInSoftware(target.mode, target.softwareFallback,\n'
    '                isHardwareDecoder(target.player), kind, target.output.videoDecodeError())) {'
)

# Set an explicit known-good decoder before each file is opened.
patch(
    '            active.setPropertyString("hwdec", activeHwdec(target));\n'
    '            target.pendingSeek = target.position > 0;',
    '            active.setPropertyString("hwdec", activeHwdec(target));\n'
    '            active.setPropertyString("video-aspect-override", "no");\n'
    '            target.pendingSeek = target.position > 0;'
)
patch(
    '            target.player.setPropertyString("hwdec", activeHwdec(target));\n'
    '            target.player.setPropertyString("force-window", "yes");',
    '            target.player.setPropertyString("hwdec", activeHwdec(target));\n'
    '            target.player.setPropertyString("video-aspect-override", "no");\n'
    '            target.player.setPropertyString("force-window", "yes");'
)
patch(
    '            option(active, "opengl-es", "yes"); option(active, "hwdec", MpvDecodeMode.stored(decoderMode()).hwdec);',
    '            option(active, "opengl-es", "yes"); option(active, "hwdec",\n'
    '                isMiTV4() && MpvDecodeMode.stored(decoderMode()) == MpvDecodeMode.AUTOMATIC\n'
    '                    ? "mediacodec-copy" : MpvDecodeMode.stored(decoderMode()).hwdec);'
)

# Attempt geometry correction on first render and every 500ms until conditions
# become available. Keep hwdec unchanged in all cases.
patch(
    '        target.output.configured = Boolean.TRUE.equals(player.getPropertyBoolean("vo-configured"));\n'
    '        Boolean coreIdle',
    '        target.output.configured = Boolean.TRUE.equals(player.getPropertyBoolean("vo-configured"));\n'
    '        maybeApplyPortraitAspect(target);\n'
    '        Boolean coreIdle'
)
patch(
    '                if (target.outputReady) {\n'
    '                    reportProgress(target);\n'
    '                    checkDecodeStall(target);',
    '                if (target.outputReady) {\n'
    '                    maybeApplyPortraitAspect(target);\n'
    '                    reportProgress(target);\n'
    '                    checkDecodeStall(target);'
)

patch(
    '                .put("software_fallback", target.softwareFallback)\n',
    '                .put("software_fallback", target.softwareFallback)\n'
    '                .put("mitv4_hwdec_copy_test", isMiTV4())\n'
    '                .put("portrait_aspect_fixed", target.portraitAspectFixed)\n'
    '                .put("portrait_aspect_note", target.portraitAspectNote)\n'
)
patch(
    '                fields.put("video_decoder", target.decoder).put("hwdec_current", property(player, "hwdec-current"));',
    '                fields.put("video_decoder", target.decoder).put("hwdec_current", property(player, "hwdec-current"));\n'
    '                fields.put("source_demux_w", positive(player.getPropertyInt("current-tracks/video/demux-w")))\n'
    '                    .put("source_demux_h", positive(player.getPropertyInt("current-tracks/video/demux-h")))\n'
    '                    .put("aspect_override_actual", property(player, "video-aspect-override"));'
)

print("V4: restored MediaCodec COPY, blocked application auto-CPU on MiTV4, set aspect override probe.")
