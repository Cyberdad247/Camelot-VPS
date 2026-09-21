use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use unicode_normalization::UnicodeNormalization;

pub const GLYPH_GRAMMAR: &str = "camelot-nukg-glyph/1";
pub const GLYPH_AUTHORITY_SEMANTICS: &str = "glyph-not-authority";
pub const MAX_GLYPH_BYTES: usize = 16 * 1024;
pub const MAX_GLYPH_TOKENS: usize = 4096;
pub const MAX_GROUP_DEPTH: usize = 32;

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum GlyphOperator {
    Separator,
    Compose,
    Transform,
    Compare,
    Prefer,
    Implies,
    OpenGroup,
    CloseGroup,
    Colon,
    Version,
    Digest,
    Qualified,
    Conditional,
    RejectedBaseline,
    Provisional,
    Unresolved,
    Contested,
    Revisit,
    Dot,
}

impl GlyphOperator {
    pub fn symbol(self) -> &'static str {
        match self {
            Self::Separator => "⋮",
            Self::Compose => "⊞",
            Self::Transform => "→",
            Self::Compare => "≫",
            Self::Prefer => "⊳",
            Self::Implies => "⟹",
            Self::OpenGroup => "[",
            Self::CloseGroup => "]",
            Self::Colon => ":",
            Self::Version => "@",
            Self::Digest => "#",
            Self::Qualified => "✓",
            Self::Conditional => "⚠",
            Self::RejectedBaseline => "⊘",
            Self::Provisional => "~",
            Self::Unresolved => "?",
            Self::Contested => "!",
            Self::Revisit => "↺",
            Self::Dot => "·",
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", content = "value", rename_all = "SCREAMING_SNAKE_CASE")]
pub enum GlyphToken {
    Atom(String),
    Operator(GlyphOperator),
}

impl GlyphToken {
    fn rendered(&self) -> String {
        match self {
            Self::Atom(value) => value.clone(),
            Self::Operator(operator) => operator.symbol().to_string(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct GlyphAst {
    pub grammar: String,
    pub authority_semantics: String,
    pub raw: String,
    pub normalized: String,
    pub normalized_sha256: String,
    pub tokens: Vec<GlyphToken>,
}

impl GlyphAst {
    pub fn parse(seed: &str) -> Result<Self, String> {
        if seed.trim().is_empty() {
            return Err("glyph seed cannot be empty".into());
        }
        if seed.len() > MAX_GLYPH_BYTES {
            return Err(format!("glyph seed exceeds {MAX_GLYPH_BYTES} bytes"));
        }

        let mut tokens = Vec::new();
        let mut atom = String::new();
        let mut group_depth = 0usize;

        let flush_atom = |tokens: &mut Vec<GlyphToken>, atom: &mut String| {
            if !atom.is_empty() {
                let normalized: String = atom.nfc().collect();
                tokens.push(GlyphToken::Atom(normalized));
                atom.clear();
            }
        };

        for scalar in seed.chars() {
            if scalar.is_whitespace() {
                flush_atom(&mut tokens, &mut atom);
                continue;
            }
            if is_forbidden_scalar(scalar) {
                return Err(format!(
                    "glyph contains forbidden or invisible scalar U+{:04X}",
                    scalar as u32
                ));
            }

            if let Some(operator) = operator_for(scalar) {
                flush_atom(&mut tokens, &mut atom);
                match operator {
                    GlyphOperator::OpenGroup => {
                        group_depth = group_depth
                            .checked_add(1)
                            .ok_or("glyph group depth overflow")?;
                        if group_depth > MAX_GROUP_DEPTH {
                            return Err(format!(
                                "glyph nesting exceeds maximum depth {MAX_GROUP_DEPTH}"
                            ));
                        }
                    }
                    GlyphOperator::CloseGroup => {
                        if group_depth == 0 {
                            return Err("glyph contains unmatched closing group".into());
                        }
                        group_depth -= 1;
                    }
                    _ => {}
                }
                tokens.push(GlyphToken::Operator(operator));
            } else if is_atom_scalar(scalar) {
                atom.push(scalar);
            } else {
                return Err(format!(
                    "glyph contains unsupported scalar U+{:04X}",
                    scalar as u32
                ));
            }

            if tokens.len() > MAX_GLYPH_TOKENS {
                return Err(format!("glyph exceeds {MAX_GLYPH_TOKENS} tokens"));
            }
        }

        flush_atom(&mut tokens, &mut atom);

        if group_depth != 0 {
            return Err("glyph contains unclosed group".into());
        }
        if tokens.is_empty() {
            return Err("glyph contains no semantic tokens".into());
        }
        if tokens.len() > MAX_GLYPH_TOKENS {
            return Err(format!("glyph exceeds {MAX_GLYPH_TOKENS} tokens"));
        }

        let normalized = tokens
            .iter()
            .map(GlyphToken::rendered)
            .collect::<Vec<_>>()
            .join("");
        let normalized_sha256 = sha256_prefixed(normalized.as_bytes());

        Ok(Self {
            grammar: GLYPH_GRAMMAR.into(),
            authority_semantics: GLYPH_AUTHORITY_SEMANTICS.into(),
            raw: seed.into(),
            normalized,
            normalized_sha256,
            tokens,
        })
    }
}

fn operator_for(value: char) -> Option<GlyphOperator> {
    Some(match value {
        '⋮' => GlyphOperator::Separator,
        '⊞' => GlyphOperator::Compose,
        '→' => GlyphOperator::Transform,
        '≫' => GlyphOperator::Compare,
        '⊳' => GlyphOperator::Prefer,
        '⟹' => GlyphOperator::Implies,
        '[' => GlyphOperator::OpenGroup,
        ']' => GlyphOperator::CloseGroup,
        ':' => GlyphOperator::Colon,
        '@' => GlyphOperator::Version,
        '#' => GlyphOperator::Digest,
        '✓' => GlyphOperator::Qualified,
        '⚠' => GlyphOperator::Conditional,
        '⊘' => GlyphOperator::RejectedBaseline,
        '~' => GlyphOperator::Provisional,
        '?' => GlyphOperator::Unresolved,
        '!' => GlyphOperator::Contested,
        '↺' => GlyphOperator::Revisit,
        '·' => GlyphOperator::Dot,
        _ => return None,
    })
}

fn is_atom_scalar(value: char) -> bool {
    value.is_alphanumeric() || matches!(value, '_' | '-' | '.' | '+' | '/' | '&')
}

fn is_forbidden_scalar(value: char) -> bool {
    if value.is_control() {
        return true;
    }
    matches!(
        value as u32,
        0x200B..=0x200F
            | 0x202A..=0x202E
            | 0x2060
            | 0x2066..=0x2069
            | 0xFEFF
    )
}

fn sha256_prefixed(data: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(data);
    format!("sha256:{:x}", hasher.finalize())
}

#[cfg(test)]
mod tests {
    use super::*;

    const THREAD_SEED: &str =
        "νKG⋮MoE5⊞Pent→Frac→Merlin→Knight→Fab≫CP⊳Fab⟹[6✓ 3⚠ 3⊘]⊳MTHD:1→M→A";

    #[test]
    fn parses_thread_seed_deterministically() {
        let parsed = GlyphAst::parse(THREAD_SEED).expect("thread glyph");
        assert_eq!(parsed.grammar, GLYPH_GRAMMAR);
        assert_eq!(parsed.authority_semantics, GLYPH_AUTHORITY_SEMANTICS);
        assert_eq!(
            parsed.normalized,
            "νKG⋮MoE5⊞Pent→Frac→Merlin→Knight→Fab≫CP⊳Fab⟹[6✓3⚠3⊘]⊳MTHD:1→M→A"
        );
        assert!(parsed.normalized_sha256.starts_with("sha256:"));
        assert_eq!(parsed.normalized_sha256.len(), 71);
    }

    #[test]
    fn keeps_baseline_and_uncertainty_markers_explicit() {
        let parsed = GlyphAst::parse("Fab~⊘@v3↺").expect("qualified disposition");
        assert_eq!(parsed.normalized, "Fab~⊘@v3↺");
        assert!(parsed
            .tokens
            .contains(&GlyphToken::Operator(GlyphOperator::RejectedBaseline)));
        assert!(parsed
            .tokens
            .contains(&GlyphToken::Operator(GlyphOperator::Revisit)));
    }

    #[test]
    fn whitespace_does_not_change_normalized_digest() {
        let compact = GlyphAst::parse("A→B⊳C").unwrap();
        let spaced = GlyphAst::parse(" A → B  ⊳ C ").unwrap();
        assert_eq!(compact.normalized, spaced.normalized);
        assert_eq!(compact.normalized_sha256, spaced.normalized_sha256);
    }

    #[test]
    fn rejects_unbalanced_groups() {
        assert!(GlyphAst::parse("A→[B").unwrap_err().contains("unclosed"));
        assert!(GlyphAst::parse("A→B]").unwrap_err().contains("unmatched"));
    }

    #[test]
    fn rejects_bidi_and_zero_width_controls() {
        assert!(GlyphAst::parse("Merlin\u{202E}v2")
            .unwrap_err()
            .contains("forbidden"));
        assert!(GlyphAst::parse("Merlin\u{200B}v2")
            .unwrap_err()
            .contains("forbidden"));
    }

    #[test]
    fn rejects_unknown_punctuation_instead_of_guessing() {
        assert!(GlyphAst::parse("A{B}").unwrap_err().contains("unsupported"));
    }
}
