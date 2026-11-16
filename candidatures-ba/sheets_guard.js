(function createSheetsGuard(tools, { spreadsheetId, sheetId, cell = "B83", rowIndex = 82 }) {
    const free = "LIBRE";
    const getData = value => {
        while (value.structuredContent) value = value.structuredContent;
        return value;
    };

    async function read() {
        const response = await tools.mcp__codex_apps__google_drive_get_spreadsheet_range({
            spreadsheet_id: spreadsheetId, sheet_name: "Mandat", range: cell,
        });
        const value = getData(response).values?.[0]?.[0];
        if (response.isError || !value) throw new Error("Réservation Sheets illisible");
        return value;
    }

    async function change(expected, replacement) {
        const response = await tools.mcp__codex_apps__google_drive_batch_update_spreadsheet({
            spreadsheet_id: spreadsheetId,
            requests: [{ findReplace: {
                find: expected, replacement, matchEntireCell: true, matchCase: true, includeFormulas: false,
                range: { sheetId, startRowIndex: rowIndex, endRowIndex: rowIndex + 1, startColumnIndex: 1, endColumnIndex: 2 },
            } }],
        });
        const result = getData(response);
        const counts = result.replies?.[0]?.findReplace;
        if (response.isError || !counts) throw new Error("Résultat de la réservation à réconcilier");
        return counts.occurrencesChanged ?? 0;
    }

    function checkToken(token) {
        if (!/^SFD10_[a-zA-Z0-9_-]{16,100}$/.test(token)) throw new Error("Identifiant de tentative invalide");
    }

    async function acquire(token) {
        checkToken(token);
        const count = await change(free, token);
        if (count === 0) return false;
        if (count !== 1 || await read() !== token) throw new Error("Réservation non vérifiée");
        return true;
    }

    async function release(token) {
        checkToken(token);
        const count = await change(token, free);
        if (count !== 1) throw new Error("La tentative a perdu sa réservation");
    }

    return { acquire, release, read };
})
