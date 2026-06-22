"""
Limpieza de tracks residuales con prefijo "AUTO_" en un draft de CapCut.

Solo elimina tracks de imported_tracks (los provenientes del JSON existente)
cuyo nombre empiece con "AUTO_".  Los tracks manuales del usuario nunca
se tocan.
"""


class Cleaner:
    """Elimina tracks residuales "AUTO_" de un script de CapCut ya cargado."""

    PREFIJO = "AUTO_"

    def __init__(self, script):
        """
        Args:
            script: objeto ScriptFile devuelto por DraftFolder.load_template()
        """
        self.script = script

    # ── API pública ────────────────────────────────────────────────────────────

    def limpiar_tracks_texto(self) -> int:
        """Elimina tracks de texto con prefijo AUTO_.

        Returns:
            Cantidad de tracks eliminados.
        """
        return self._eliminar_tracks("text")

    def limpiar_tracks_audio(self) -> int:
        """Elimina tracks de audio con prefijo AUTO_.

        Returns:
            Cantidad de tracks eliminados.
        """
        return self._eliminar_tracks("audio")

    def limpiar_todos(self) -> dict:
        """Limpia texto Y audio en una sola llamada.

        Returns:
            {"texto": n_texto, "audio": n_audio}
        """
        return {
            "texto": self.limpiar_tracks_texto(),
            "audio": self.limpiar_tracks_audio(),
        }

    def limpiar_autocaption_nativo(self) -> int:
        """Elimina SOLO los segmentos de auto-caption nativo de CapCut (sin
        editar), detectados por tener 'recognize_task_id' poblado en su
        material. Esto distingue auto-caption real de texto manual del
        usuario que pueda estar en un track sin nombre.

        Llamar EXPLICITAMENTE (no es parte de limpiar_tracks_texto/limpiar_
        todos) porque borra contenido que no tiene prefijo AUTO_ - solo se
        debe usar despues de haber extraido sus datos (texto+timings).

        Nota de implementacion: imported_materials['texts'] son dicts
        crudos del JSON (no objetos), indexados por 'id'. Se cruza cada
        segmento (que solo trae material_id) contra ese diccionario.

        Returns:
            Cantidad de segmentos eliminados.
        """
        materiales_texto = self.script.imported_materials.get("texts", []) or []
        ids_autocaption = {
            m.get("id") for m in materiales_texto if m.get("recognize_task_id")
        }
        if not ids_autocaption:
            return 0

        eliminados = 0
        for track in list(self.script.imported_tracks):
            if not self._es_tipo_track(track, "text"):
                continue
            a_borrar = [
                seg for seg in track.segments
                if seg.material_id in ids_autocaption
            ]
            for seg in a_borrar:
                try:
                    track.segments.remove(seg)
                    eliminados += 1
                except ValueError:
                    pass
        return eliminados

    # ── Internos ───────────────────────────────────────────────────────────────

    def _eliminar_tracks(self, tipo: str) -> int:
        """Elimina de imported_tracks los que sean del tipo indicado y "AUTO_".

        Args:
            tipo: "text" o "audio"

        Returns:
            Cantidad de tracks eliminados.
        """
        residuales = [
            t for t in self.script.imported_tracks
            if self._es_tipo_track(t, tipo) and t.name.startswith(self.PREFIJO)
        ]
        for track in residuales:
            try:
                self.script.imported_tracks.remove(track)
            except ValueError:
                if hasattr(self.script, "remove_track"):
                    self.script.remove_track(track)
        return len(residuales)

    def _es_tipo_track(self, track, tipo: str) -> bool:
        """Compatibilidad entre distintas formas de exponer el tipo de track."""
        track_type = getattr(track, "track_type", None)
        if track_type is not None:
            return getattr(track_type, "name", "") == tipo
        return getattr(track, "type", "") == tipo