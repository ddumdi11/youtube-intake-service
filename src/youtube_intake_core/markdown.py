"""Markdown-Builder im Somas-Stil (Core, server-frei).

Erzeugt exakt den Markdown-Body, der bisher Teil des process()-Ergebnisses war.
Die Wire-Form darf sich nicht aendern.
"""


def build_markdown(
    *,
    title: str,
    channel: str,
    duration_formatted: str,
    url: str,
    thumbnails: dict,
    transcript_text: str,
) -> str:
    transcript_markdown = transcript_text if transcript_text else "_Kein Transkript verfuegbar._"
    alt_text = f'Thumbnail zum Video „{title}“'

    return f"""# {title}

![{alt_text}]({thumbnails['maxres']})

**Kanal:** {channel}
**Dauer:** {duration_formatted}
**URL:** [{url}]({url})

> Falls das Bild nicht angezeigt wird, diese Varianten testen:
> - [MaxRes]({thumbnails['maxres']})
> - [SD]({thumbnails['sd']})
> - [HQ]({thumbnails['hq']})

## Transkript

{transcript_markdown}
"""
