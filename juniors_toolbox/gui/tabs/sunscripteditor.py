from dataclasses import dataclass
from typing import Optional
from juniors_toolbox.gui.tabs import A_DockingInterface
from PySide6.QtCore import Qt, QRegularExpression
from PySide6.QtGui import (QRegularExpressionValidator, QSyntaxHighlighter, QColor, QFont,
                           QTextBlock, QTextBlockFormat, QTextCharFormat, QTextDocument,
                           QTextFormat)
from PySide6.QtWidgets import (QLabel, QListView, QListWidget, QTextEdit,
                               QWidget)


@dataclass
class HighlighingRule:
    regexp: QRegularExpression
    format: QTextCharFormat
    block: bool


class SunscriptSyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, parent: Optional[QTextDocument] = None) -> None:
        self.highlightingRules = []

    def get_keyword_format(self) -> QTextCharFormat:
        textFormat = QTextCharFormat()
        textFormat.setForeground(QColor(190, 132, 190, 255))
        textFormat.setFontWeight(QFont.Bold)
        return textFormat

    def get_statement_format(self) -> QTextCharFormat:
        textFormat = QTextCharFormat()
        textFormat.setForeground(QColor(83, 154, 211, 255))
        return textFormat

    def get_block_format(self) -> QTextCharFormat:
        textFormat = QTextCharFormat()
        textFormat.setForeground(QColor(252, 212, 0, 255))
        return textFormat

    def get_type_format(self) -> QTextCharFormat:
        textFormat = QTextCharFormat()
        textFormat.setForeground(QColor(73, 183, 142, 255))
        return textFormat

    def get_comment_format(self) -> QTextCharFormat:
        textFormat = QTextCharFormat()
        textFormat.setForeground(QColor(105, 151, 84, 255))
        textFormat.setFontItalic(True)
        return textFormat
    
    def get_keywords(self) -> dict[str, HighlighingRule]:
        keywordFormat = self.get_keyword_format()
        return {
            "break": HighlighingRule(
                QRegularExpression("break"),
                keywordFormat,
                False
            ),
            "continue": HighlighingRule(
                QRegularExpression("continue"),
                keywordFormat,
                False
            ),
            "return": HighlighingRule(
                QRegularExpression("return"),
                keywordFormat,
                False
            ),
            "yield": HighlighingRule(
                QRegularExpression("yield"),
                keywordFormat,
                False
            ),
            "exit": HighlighingRule(
                QRegularExpression("exit"),
                keywordFormat,
                False
            ),
            "lock": HighlighingRule(
                QRegularExpression("lock"),
                keywordFormat,
                False
            ),
            "unlock": HighlighingRule(
                QRegularExpression("unlock"),
                keywordFormat,
                False
            ),
            "const": HighlighingRule(
                QRegularExpression("const"),
                keywordFormat,
                False
            ),
            "var": HighlighingRule(
                QRegularExpression("var"),
                keywordFormat,
                False
            ),
            "local": HighlighingRule(
                QRegularExpression("local"),
                keywordFormat,
                False
            )
        }

    def get_statements(self) -> dict[str, HighlighingRule]:
        keywordFormat = self.get_keyword_format()
        return {
            "import": HighlighingRule(
                QRegularExpression("import"),
                keywordFormat,
                False
            ),
            "builtin": HighlighingRule(
                QRegularExpression("builtin"),
                keywordFormat,
                False
            ),
            "function": HighlighingRule(
                QRegularExpression("function"),
                keywordFormat,
                False
            )
        }

    def get_control_flows(self) -> dict[str, HighlighingRule]:
        keywordFormat = self.get_keyword_format()
        return {
            "do": HighlighingRule(
                QRegularExpression("do"),
                keywordFormat,
                False
            ),
            "for": HighlighingRule(
                QRegularExpression("for"),
                keywordFormat,
                False
            ),
            "if": HighlighingRule(
                QRegularExpression("if"),
                keywordFormat,
                False
            ),
            "else": HighlighingRule(
                QRegularExpression("else"),
                keywordFormat,
                False
            ),
            "while": HighlighingRule(
                QRegularExpression("while"),
                keywordFormat,
                False
            )
        }

    def get_blocks(self) -> dict[str, HighlighingRule]:
        blockFormat = self.get_block_format()
        return {
            "do": HighlighingRule(
                QRegularExpression("do"),
                blockFormat,
                True
            ),
            "for": HighlighingRule(
                QRegularExpression("for"),
                blockFormat,
                True
            ),
            "if": HighlighingRule(
                QRegularExpression("if"),
                blockFormat,
                True
            ),
            "else": HighlighingRule(
                QRegularExpression("else"),
                blockFormat,
                True
            ),
        }

    def get_comments(self) -> dict[str, HighlighingRule]:
        commentFormat = self.get_comment_format()
        return {
            "multi-comment-start": HighlighingRule(
                QRegularExpression("/\*"),
                commentFormat,
                True
            ),
            "multi-comment-end": HighlighingRule(
                QRegularExpression("\*/"),
                commentFormat,
                True
            ),
            "comment": HighlighingRule(
                QRegularExpression("//"),
                commentFormat,
                True
            ),
            
        }

    def get_operators(self) -> dict[str, HighlighingRule]:
        return [
            # Assignment
            QRegularExpression("=(?!=)"),

            # Augment
            "+=",
            "-=",
            "*=",
            "/=",
            "%=",
            "&=",
            "|=",
            "<<=",
            ">>=",

            # Arithmetic
            "++",
            "--",
            "+",
            "-",
            "*",
            "/",
            "%",

            # Logical
            "!",
            "&&",
            "||",

            # Bitwise
            "~",
            "<<",
            ">>",
            "&",
            "|",

            # Relational
            "<=",
            ">=",
            "<",
            ">",

            # Logical
            "==",
            "!=",

            # Ternary
            "?",
            ":"
        ]

    def get_punctuation(self) -> dict[str, HighlighingRule]:
        return [
            ";",
            ","
        ]