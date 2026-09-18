"""发布说明提取脚本：从 CHANGELOG.md 提取指定版本的更新内容，并自动追加 Full Changelog 链接

用法：
    python scripts/extract_changelog.py <版本或标签> [输出文件]

示例：
    python scripts/extract_changelog.py v1.0.0 release_notes.md   # 写入文件（CI 中使用，自动追加 Full Changelog 链接）
    python scripts/extract_changelog.py v1.0.0                    # 打印到标准输出（仅更新内容）

说明：
    - 匹配 CHANGELOG.md 中形如 `## [v1.0.0] - 日期` 的段落（'v' 前缀可省略），提取到下一个版本标题前为止
    - 未找到对应版本时报错退出，避免发布出没有说明内容的 Release
    - 写入文件模式下，若设置了 GITHUB_SERVER_URL 与 GITHUB_REPOSITORY 环境变量（GitHub Actions 自带），
      会追加 Full Changelog 链接：能定位到上一版本标签时用 compare 对比页，首个版本则用 commits 列表页
"""
import os
import re
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANGELOG_FILE = 'CHANGELOG.md'


def extract_version_section(version, changelog_text):
    """提取 CHANGELOG 中指定版本的正文段落（不含版本标题行），找不到时返回空字符串"""
    version = version.lstrip('vV')
    pattern = re.compile(
        r'^##\s*\[v?' + re.escape(version) + r'\][^\n]*\n(.*?)(?=^##\s*\[|\Z)',
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(changelog_text)
    return match.group(1).strip() if match else ''


def get_previous_tag(tag):
    """用 git describe 查找该标签之前的最近版本标签；找不到（如首个版本）时返回空字符串"""
    try:
        result = subprocess.run(
            ['git', 'describe', '--tags', '--abbrev=0', tag + '^'],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            cwd=PROJECT_ROOT,
        )
    except OSError:
        return ''
    return result.stdout.strip() if result.returncode == 0 else ''


def build_full_changelog_url(tag):
    """构造 Full Changelog 链接；缺少仓库环境变量（如本地普通运行）时返回空字符串"""
    server = os.environ.get('GITHUB_SERVER_URL', '').rstrip('/')
    repo = os.environ.get('GITHUB_REPOSITORY', '')
    if not server or not repo:
        return ''
    previous_tag = get_previous_tag(tag)
    if previous_tag:
        return server + '/' + repo + '/compare/' + previous_tag + '...' + tag
    return server + '/' + repo + '/commits/' + tag


def main():
    # 部分环境（如英文系统的 CI）输出编码无法表示中文（如 cp1252），打印中文时会抛
    # UnicodeEncodeError；探测到无法编码中文时将输出流切换为 UTF-8
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, 'reconfigure'):
            try:
                '中文'.encode(stream.encoding or 'utf-8')
            except (UnicodeEncodeError, LookupError):
                try:
                    stream.reconfigure(encoding='utf-8', errors='replace')
                except Exception:
                    pass

    if len(sys.argv) < 2:
        print('用法：python scripts/extract_changelog.py <版本或标签> [输出文件]')
        return 1

    version = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else ''

    changelog_path = os.path.join(PROJECT_ROOT, CHANGELOG_FILE)
    try:
        with open(changelog_path, encoding='utf-8') as f:
            text = f.read()
    except OSError as e:
        print('错误：读取 ' + CHANGELOG_FILE + ' 失败：' + str(e))
        return 1

    section = extract_version_section(version, text)
    if not section:
        print('错误：' + CHANGELOG_FILE + ' 中未找到版本 ' + version + ' 的段落，请先补充更新日志再发布')
        return 1

    if out_path:
        lines = [section]
        url = build_full_changelog_url(version)
        if url:
            lines.append('**Full Changelog**: ' + url)
        try:
            with open(out_path, 'w', encoding='utf-8', newline='\n') as f:
                f.write('\n\n'.join(lines) + '\n')
        except OSError as e:
            print('错误：写入 ' + out_path + ' 失败：' + str(e))
            return 1
        print('已生成发布说明：' + out_path)
    else:
        print(section)
    return 0


if __name__ == '__main__':
    sys.exit(main())
