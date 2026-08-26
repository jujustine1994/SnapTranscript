"""locales/zh_cn.py — 简体中文

改这里的译文不影响任何逻辑：程序一律用 key 比对。改错最坏的情况只是
画面显示怪怪的。

⚠ 带变量的消息一律用**具名** placeholder（{path} 而不是 {0}）——翻译时
语序一变，位置参数就错位。四种语言的 placeholder 集合必须完全一致，
tests/test_i18n.py 会检查。

⚠ 本档由 AI 产出，**未经母语者校对**。改 value 不要动 key。
"""

from __future__ import annotations

STRINGS: dict[str, str] = {
    # ---- 区块标题 ----
    "gui.frame.source":            " 音频来源 ",
    "gui.frame.range":             " 提取范围 ",
    "gui.frame.cut":               " 切割设置 ",
    "gui.frame.progress":          " 处理进度 ",

    # ---- 音频来源 ----
    "gui.radio.local":             "本地上传",
    "gui.radio.youtube":           "YouTube 下载",
    "gui.btn.select_file":         "选择文件",
    "gui.lbl.yt_url":              "YouTube 网址：",
    "gui.lbl.save_as":             "保存为：",
    "gui.btn.save_as":             "另存为",
    "gui.radio.download_transcribe": "下载后立即转录",
    "gui.radio.download_only":     "仅下载音频（不需 API Key）",

    # ---- 提取范围 ----
    "gui.chk.range_enabled":       "只处理音频的一部分",
    "gui.lbl.range_start":         "起始时间：",
    "gui.lbl.range_end":           "结束时间：",
    "gui.lbl.time_format_hint":    "（HH:MM:SS，例如 00:10:00）",
    "gui.lbl.range_note":          "⚠️ 下方切割点为原始音频的绝对时间，需落在此范围内才会生效",

    # ---- 切割设置 ----
    "gui.radio.cut_auto":          "自动（每 {minutes} 分钟切一段）",
    "gui.lbl.min_seg_prefix":      "└ 尾段不足",
    "gui.lbl.min_seg_suffix":      "分钟就并入前一段（填 0 不合并）",
    "gui.radio.cut_custom":        "自定义切割点",
    "gui.lbl.custom_points":       "输入切割时间点（HH:MM:SS，每行一个）：",

    # ---- API Key ----
    "gui.btn.show":                "显示",
    "gui.btn.save_key":            "保存",
    "gui.lbl.api_saved":           "✓ 已保存",
    "gui.lbl.api_notice":          "🔒 API Key 仅保存于本机 .env 文件，请勿将 Key 提供给他人。",
    "gui.link.api_help":           "如何获取 API Key？",

    # ---- API Key 说明窗口 ----
    "gui.dlg.api_help.title":      "如何获取 Gemini API Key",
    "gui.dlg.api_help.steps":      "申请步骤",
    "gui.dlg.api_help.step1":      "1. 点击下方链接，前往 Google AI Studio",
    "gui.dlg.api_help.step2":      "2. 使用 Google 账号登录",
    "gui.dlg.api_help.step3":      "3. 点击「Create API key」",
    "gui.dlg.api_help.step4":      "4. 选择「Create API key in new project」",
    "gui.dlg.api_help.step5":      "5. 复制生成的 Key，粘贴到 SnapTranscript 的 API Key 栏位",
    "gui.dlg.api_help.notice":     "⚠️  注意：申请后请确认 API Key 状态显示为「Free tier」，\n"
                                   "若显示「Set up billing」代表尚未启用免费方案，\n"
                                   "请勿输入信用卡，直接使用即可享有免费额度。",
    "gui.btn.close":               "关闭",

    # ---- 开始行 / 进度区 ----
    "gui.btn.start_transcribe":    "▶  开始转录",
    "gui.btn.start_download":      "▶  开始下载",
    "gui.chk.auto_retry":          "自动重试",
    "gui.status.idle":             "等待开始...",
    "gui.status.preparing":        "准备中...",
    "gui.status.error":            "发生错误，请查看上方记录",
    "gui.btn.open_folder":         "打开文件夹",
    "gui.log.intro":               "请选择音频来源，设置完成后按「开始」。\n",

    # ---- 关闭窗口确认 ----
    "gui.dlg.closing.title":       "任务进行中",
    "gui.dlg.closing.body":        "转录还在进行中，现在关闭会中断任务。\n\n"
                                   "已完成的段落尚未写入文件，关闭后会丢失，\n"
                                   "需要重新开始转录。\n\n"
                                   "确定要关闭吗？",

    # ---- 补跑 ----
    "gui.btn.retry_failed":        "重试失败的段落",
    "gui.btn.retry_failed_n":      "重试失败的 {count} 段",
    "gui.btn.continue_unfinished": "继续未完成的 {count} 段",
    "gui.msg.unfinished_generic":  "部分段落未完成",
    "gui.msg.n_failed":            "{count} 段失败",
    "gui.msg.n_pending":           "{count} 段未处理",
    "gui.msg.list_sep":            "、",
    "gui.dlg.audio_missing.title": "找不到音频文件",
    "gui.dlg.audio_missing.body":  "原始音频已不存在，无法补跑：\n{path}",
    "gui.log.retry_start":         "\n开始补跑 {count} 个失败段落...",
    "gui.log.transcript_updated":  "\n转录稿已更新：{path}",

    # ---- 文件对话框 ----
    "gui.dlg.save_title":          "选择保存位置与文件名",
    "gui.dlg.open_title":          "选择音频文件",
    "gui.filetype.mp3":            "MP3 音频",
    "gui.filetype.audio":          "音频文件",
    "gui.filetype.all":            "所有文件",

    # ---- 输入验证 ----
    "gui.dlg.error.title":         "错误",
    "gui.dlg.format_error.title":  "格式错误",
    "gui.msg.no_file":             "请先选择音频文件",
    "gui.msg.no_url":              "请输入 YouTube 网址",
    "gui.msg.no_save_path":        "请点「另存为」选择保存位置与文件名",
    "gui.msg.no_api_key":          "请输入 Gemini API Key",

    # ---- 执行过程 ----
    "gui.log.downloading":         "正在下载 YouTube 音频，请稍候...",
    "gui.log.download_done":       "下载完成：{name}",
    "gui.status.downloading_pct":  "下载中... {percent}%  ({done} / {total} MB{speed})",
    "gui.status.downloading_size": "下载中... {done} MB{speed}",
    "gui.log.reading_audio":       "读取音频：{name}",
    "gui.log.total_duration":      "总时长：{duration}",
    "gui.log.range":               "提取范围：{start} → {end}",
    "gui.log.segments_planned":    "共 {count} 段，开始处理...",
    "gui.log.transcript_saved":    "\n转录稿已保存：{path}",

    # ---- 结果 ----
    "gui.dlg.transcribe_failed.title": "转录失败",
    "gui.lbl.downloaded":          "已下载：{path}",
    "gui.dlg.download_done.title": "下载完成",
    "gui.dlg.download_done.body":  "音频已保存至：\n{path}",
    "gui.lbl.output":              "输出：{path}",
    "gui.lbl.output_partial":      "输出：{path}（{ok}/{total} 段成功）",
    "gui.lbl.output_aborted":      "输出（部分完成）：{path}",
    "gui.dlg.partial.title":       "部分完成",
    "gui.dlg.partial.body":        "转录稿已保存（{ok}/{total} 段成功，{detail}）：\n"
                                   "{path}\n\n"
                                   "未完成的段落在文件中标记为占位符，可按「{button}」补跑。",
    "gui.dlg.done.title":          "完成",
    "gui.dlg.done.body":           "转录稿已保存：\n{path}",

    # ---- job.py ----
    "job.status.segments_done":    "{done} / {total} 段完成",
    "job.log.cutting":             "\n[{index}/{total}] 切割 {start} → {end}...",
    "job.log.uploading":           "[{index}/{total}] 上传至 Gemini，等待转录...",
    "job.log.segment_done":        "[{index}/{total}] 完成",
    "job.log.error":               "[错误] {reason}",
    "job.log.auto_retrying":       "[{index}/{total}] 自动重试中... ({count}/{max})",
    "job.log.retrying":            "[{index}/{total}] 重试中...",
    "job.log.marked_failed":       "[{index}/{total}] {reason}，标记后继续",
    "job.log.merging":             "\n合并转录稿...",
    "job.status.retry_wait":       "第 {index} 段重试中... {seconds} 秒 ({count}/{max})",
    "job.msg.cut_failed":          "第 {index} 段切割失败，请确认 ffmpeg 是否正常运作",
    "job.msg.quota_exhausted":     "已达 Gemini API 用量上限（可能是短时间内请求过多，或当日额度用尽）。"
                                   "已完成的段落已保存，请稍后用「重试失败的段落」补跑。",
    "job.msg.retry_exhausted":     "{reason}，已自动重试 {max} 次仍失败",
    "job.msg.retry_cancelled":     "{reason}（用户取消重试）",
    "job.msg.ask_retry":           "{reason}，是否重试？",

    # ---- 错误消息 ----
    "err.audio.not_found":         "找不到音频文件：{path}\n"
                                   "文件可能已被移动、删除，或所在的 U 盘／网络磁盘已断开。",
    "err.audio.no_ffprobe":        "找不到 ffprobe（ffmpeg 的一部分）。请确认 ffmpeg 已安装并加入系统 PATH，"
                                   "在命令行执行 `ffmpeg -version` 可以验证。",
    "err.audio.bad_duration":      "无法读取音频长度：{name}\n"
                                   "这个文件可能不是有效的音频／视频文件，或文件已损坏。",
    "err.audio.download_missing":  "下载后找不到音频文件：{path}",
    "err.seg.bad_time_format":     "格式错误：「{value}」，请使用 HH:MM:SS 格式（例如 {example}）",
    "err.seg.range_required":      "请输入起始与结束时间",
    "err.seg.start_after_end":     "起始时间必须早于结束时间",
    "err.seg.min_required":        "请输入尾段合并阈值（分钟），填 0 代表不合并",
    "err.seg.min_bad_format":      "格式错误：「{value}」，请输入整数分钟（例如 5），填 0 代表不合并",
    "err.seg.min_negative":        "尾段合并阈值不能是负数，填 0 代表不合并",
    "err.seg.min_too_large":       "尾段合并阈值必须小于切割长度（{limit} 分钟），"
                                   "否则合并后的段落会长到可能超出 Gemini 的输出上限",
    "err.seg.range_beyond_audio":  "提取范围超出音频总长度，请重新设置",
    "err.gemini.file_failed":      "Gemini 文件处理失败（状态：{state}），请重试",

    # ---- 高级设置窗口 ----
    "gui.dlg.settings.title":      "高级设置",

    # ---- 版本更新（高级设置窗口内） ----
    "gui.frame.update":            " 版本更新 ",
    "gui.btn.check_update":        "检查更新",
    "gui.btn.install_update":      "一键安装",
    "gui.update.checking":         "检查中...",
    "gui.update.no_git":           "此版本无法自动更新，请至 GitHub 页面下载最新版本。",
    "gui.update.offline":          "连不上 GitHub，请确认网络连接后再试一次。",
    "gui.update.dirty":            "侦测到本机程序码有手动修改，已略过（避免覆盖你的修改）。",
    "gui.update.ahead":            "本机有尚未同步的变更，已略过（避免覆盖你的修改）。",
    "gui.update.up_to_date":       "已是最新版本。",
    "gui.update.available":        "发现新版本（{count} 笔变更），点「一键安装」更新。",
    "gui.dlg.update_confirm.title": "确认安装更新",
    "gui.dlg.update_confirm.body": "即将更新程序码，需要手动重启程序才会生效。\n\n本次变更：\n{summary}\n\n是否继续？",
    "gui.update.installing":       "安装中...",
    "gui.update.updated":          "已更新到最新版本（{commit}），请关闭程序后重新打开。",
    "gui.dlg.update_done.title":   "更新完成",
    "gui.dlg.update_done.body":    "已安装最新版本，请关闭这个窗口后重新双击启动器，让新版本生效。",
    "gui.update.error":            "检查更新失败：{msg}",
}
