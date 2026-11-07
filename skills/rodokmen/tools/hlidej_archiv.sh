#!/usr/bin/env bash
# Hlídání dávky mza_archiv.js: skončí, když (a) přijde souhrn dávky, nebo (b) 2,5 minuty nepřibyl žádný snímek
# (stránka se sama znovu načetla, zavřená karta, zamčená obrazovka …). Použití: bash tools/hlidej_archiv.sh <kniha> [limit_s]
K="$1"; LIMIT="${2:-150}"; D="$HOME/Downloads"
posl=$(date +%s); n0=$(ls "$D"/mza_"$K"_*.jpg 2>/dev/null | wc -l)
while true; do
  if ls "$D"/mza_"$K"_souhrn*.json >/dev/null 2>&1; then echo "SOUHRN"; cat "$D"/mza_"$K"_souhrn*.json; exit 0; fi
  n=$(ls "$D"/mza_"$K"_*.jpg 2>/dev/null | wc -l)
  if [ "$n" != "$n0" ]; then n0=$n; posl=$(date +%s); fi
  if [ $(( $(date +%s) - posl )) -gt "$LIMIT" ]; then
    echo "ZASEKNUTO: $LIMIT s bez nového snímku; posledni: $(ls "$D"/mza_"$K"_*.jpg 2>/dev/null | sort | tail -1)"; exit 1
  fi
  sleep 10
done
