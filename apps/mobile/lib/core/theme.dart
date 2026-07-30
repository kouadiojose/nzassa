import 'package:flutter/material.dart';

/// Design system N'Zassa — chaleureux, africain, contrasté.
abstract final class NzColors {
  static const primary = Color(0xFFE0702A); // terracotta
  static const primaryDark = Color(0xFF9C3F12);
  static const ink = Color(0xFF2B1A12); // brun profond
  static const sand = Color(0xFFFAF4EE); // fond chaud
  static const surface = Colors.white;
  static const gold = Color(0xFFF2B705);
  static const success = Color(0xFF1E8E4E);
  static const danger = Color(0xFFD64545);
  static const info = Color(0xFF2D6CDF);
  static const muted = Color(0xFF8A7A70);

  static const heroGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFF7A2E0E), Color(0xFFC85A1B), Color(0xFFE0702A)],
  );

  static const ctaGradient = LinearGradient(
    colors: [Color(0xFFC85A1B), Color(0xFFE0702A)],
  );
}

ThemeData buildNzassaTheme() {
  final scheme = ColorScheme.fromSeed(
    seedColor: NzColors.primary,
    primary: NzColors.primary,
    surface: NzColors.sand,
  );
  final base = ThemeData(useMaterial3: true, colorScheme: scheme);
  return base.copyWith(
    scaffoldBackgroundColor: NzColors.sand,
    appBarTheme: const AppBarTheme(
      backgroundColor: Colors.transparent,
      elevation: 0,
      centerTitle: false,
      foregroundColor: NzColors.ink,
      titleTextStyle: TextStyle(
        color: NzColors.ink,
        fontSize: 20,
        fontWeight: FontWeight.w800,
        letterSpacing: -0.3,
      ),
    ),
    cardTheme: CardTheme(
      color: NzColors.surface,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(20),
        side: BorderSide(color: NzColors.ink.withOpacity(0.05)),
      ),
      margin: EdgeInsets.zero,
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: NzColors.surface,
      hintStyle: const TextStyle(color: NzColors.muted),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(16),
        borderSide: BorderSide(color: NzColors.ink.withOpacity(0.08)),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(16),
        borderSide: BorderSide(color: NzColors.ink.withOpacity(0.08)),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(16),
        borderSide: const BorderSide(color: NzColors.primary, width: 1.6),
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: NzColors.primary,
        foregroundColor: Colors.white,
        minimumSize: const Size.fromHeight(52),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
      ),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: NzColors.surface,
      indicatorColor: NzColors.primary.withOpacity(0.14),
      height: 68,
      labelTextStyle: WidgetStateProperty.resolveWith(
        (states) => TextStyle(
          fontSize: 11.5,
          fontWeight:
              states.contains(WidgetState.selected) ? FontWeight.w700 : FontWeight.w500,
          color: states.contains(WidgetState.selected) ? NzColors.primaryDark : NzColors.muted,
        ),
      ),
      iconTheme: WidgetStateProperty.resolveWith(
        (states) => IconThemeData(
          color: states.contains(WidgetState.selected) ? NzColors.primaryDark : NzColors.muted,
        ),
      ),
    ),
    floatingActionButtonTheme: const FloatingActionButtonThemeData(
      backgroundColor: NzColors.ink,
      foregroundColor: NzColors.gold,
    ),
    chipTheme: base.chipTheme.copyWith(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      side: BorderSide(color: NzColors.ink.withOpacity(0.08)),
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: NzColors.ink,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
    ),
  );
}

/// Avatar coloré à partir d'un nom (initiale + teinte stable).
class NzAvatar extends StatelessWidget {
  const NzAvatar({super.key, required this.label, this.size = 44});

  final String label;
  final double size;

  static const _palette = [
    Color(0xFFE0702A),
    Color(0xFF1E8E4E),
    Color(0xFF2D6CDF),
    Color(0xFF9C27B0),
    Color(0xFFC2185B),
    Color(0xFF00838F),
    Color(0xFFF2B705),
  ];

  @override
  Widget build(BuildContext context) {
    final initial = label.isEmpty ? '?' : label.trim()[0].toUpperCase();
    final color = _palette[label.hashCode.abs() % _palette.length];
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [color, Color.lerp(color, Colors.black, 0.25)!],
        ),
        borderRadius: BorderRadius.circular(size * 0.32),
      ),
      alignment: Alignment.center,
      child: Text(
        initial,
        style: TextStyle(
          color: Colors.white,
          fontSize: size * 0.42,
          fontWeight: FontWeight.w800,
        ),
      ),
    );
  }
}

/// Pastille de statut colorée.
class NzStatusChip extends StatelessWidget {
  const NzStatusChip({super.key, required this.label, required this.color});

  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(
        label,
        style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w700),
      ),
    );
  }
}
