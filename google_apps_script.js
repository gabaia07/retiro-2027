/**
 * =========================================================================
 * GOOGLE APPS SCRIPT - INTEGRAÇÃO PIX PREMIADO RETIRO 2027
 * =========================================================================
 * 
 * INSTRUÇÕES RÁPIDAS (LEVA MENOS DE 1 MINUTO):
 * 1. Crie uma nova planilha no seu Google Drive (ex: "Controle Pix Premiado 2027").
 * 2. No menu superior da planilha, clique em: Extensões ➔ Apps Script.
 * 3. Apague qualquer código que estiver lá e cole todo este arquivo.
 * 4. Clique no botão azul no topo direito: "Implantar" (Deploy) ➔ "Nova implantação".
 * 5. Na engrenagem ao lado de "Selecione o tipo", escolha "App da Web" (Web App).
 * 6. Configure:
 *    - Descrição: Pix Premiado
 *    - Executar como: "Eu (seu email)"
 *    - Quem tem acesso: "Qualquer pessoa" (Anyone) -> ESSENCIAL para o site poder enviar os pedidos!
 * 7. Clique em "Implantar" (se pedir permissão, clique em Avançado ➔ Acessar).
 * 8. Copie a "URL do app da web" (termina com /exec).
 * 9. Cole essa URL no painel de Líderes do site (Aba Configurações ➔ Planilha Google)
 *    ou adicione no Render como a variável GOOGLE_SHEET_URL.
 * =========================================================================
 */

function getOrCreateSheet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName("Pedidos Pix Premiado");
  
  if (!sheet) {
    sheet = ss.insertSheet("Pedidos Pix Premiado");
    
    // Cabeçalhos organizados
    var headers = [
      "ID Pedido",
      "Data / Hora",
      "Nome Comprador",
      "WhatsApp / Telefone",
      "Nome Vendedor",
      "Números Comprados",
      "Qtd Pontos",
      "Valor Total (R$)",
      "Status",
      "Confirmado Por",
      "Data Confirmação",
      "Observações"
    ];
    
    sheet.appendRow(headers);
    
    // Estilização nobre do cabeçalho (Azul marinho com dourado)
    var headerRange = sheet.getRange(1, 1, 1, headers.length);
    headerRange.setBackground("#080f23");
    headerRange.setFontColor("#dfc173");
    headerRange.setFontWeight("bold");
    headerRange.setHorizontalAlignment("center");
    sheet.setFrozenRows(1);
    
    // Ajustar larguras recomendadas
    sheet.setColumnWidth(1, 80);   // ID
    sheet.setColumnWidth(2, 140);  // Data
    sheet.setColumnWidth(3, 180);  // Comprador
    sheet.setColumnWidth(4, 150);  // Telefone
    sheet.setColumnWidth(5, 150);  // Vendedor
    sheet.setColumnWidth(6, 180);  // Números
    sheet.setColumnWidth(7, 80);   // Qtd
    sheet.setColumnWidth(8, 110);  // Valor
    sheet.setColumnWidth(9, 110);  // Status
    sheet.setColumnWidth(10, 130); // Confirmado Por
    sheet.setColumnWidth(11, 140); // Data Confirmação
    sheet.setColumnWidth(12, 180); // Obs
  }
  
  return sheet;
}

// -------------------------------------------------------------------------
// POST: Recebe novos pedidos, confirmações e cancelamentos vindos do site
// -------------------------------------------------------------------------
function doPost(e) {
  try {
    var data = {};
    if (e && e.postData && e.postData.contents) {
      try {
        data = JSON.parse(e.postData.contents);
      } catch (err) {
        data = e.parameter || {};
      }
    } else if (e && e.parameter) {
      data = e.parameter;
    }

    var action = data.action || "create_order";

    // PING DE TESTE
    if (action === "ping") {
      return ContentService.createTextOutput(JSON.stringify({ success: true, message: "Conexão com Google Planilhas funcionando 100%!" }))
        .setMimeType(ContentService.MimeType.JSON);
    }

    var sheet = getOrCreateSheet();

    // 1. NOVO PEDIDO / RESERVA
    if (action === "create_order") {
      var numbersFormatted = "";
      if (data.ticket_numbers) {
        numbersFormatted = data.ticket_numbers;
      } else if (data.numbers && Array.isArray(data.numbers)) {
        numbersFormatted = data.numbers.map(function(n) {
          return ("0000" + n).slice(-4);
        }).join(", ");
      }

      sheet.appendRow([
        data.order_id,
        data.created_at || Utilities.formatDate(new Date(), "GMT-3", "dd/MM/yyyy HH:mm:ss"),
        data.buyer_name || "",
        "'" + String(data.buyer_phone || ""), // apóstrofo para manter formatação de telefone
        data.seller_name || "",
        numbersFormatted,
        data.total_tickets || (data.numbers ? data.numbers.length : 1),
        Number(data.total_amount || 0).toFixed(2),
        data.status || "pendente",
        "",
        "",
        data.notes || ""
      ]);

      // Formatar cor da linha recém-adicionada
      var lastRow = sheet.getLastRow();
      var statusCell = sheet.getRange(lastRow, 9);
      if (String(data.status).toLowerCase() === "confirmado") {
        statusCell.setBackground("#d1fae5").setFontColor("#065f46").setFontWeight("bold");
      } else {
        statusCell.setBackground("#fef3c7").setFontColor("#92400e").setFontWeight("bold");
      }

      return ContentService.createTextOutput(JSON.stringify({ success: true, message: "Pedido registrado com sucesso na planilha!" }))
        .setMimeType(ContentService.MimeType.JSON);
    }

    // 2. CONFIRMAÇÃO DE PAGAMENTO PELOS LÍDERES
    if (action === "confirm_order") {
      var values = sheet.getDataRange().getValues();
      var found = false;

      for (var i = 1; i < values.length; i++) {
        if (String(values[i][0]) === String(data.order_id)) {
          var rowIndex = i + 1;
          var statusCell = sheet.getRange(rowIndex, 9);
          statusCell.setValue("confirmado").setBackground("#d1fae5").setFontColor("#065f46").setFontWeight("bold");
          sheet.getRange(rowIndex, 10).setValue(data.confirmed_by || "Líder");
          sheet.getRange(rowIndex, 11).setValue(data.confirmed_at || Utilities.formatDate(new Date(), "GMT-3", "dd/MM/yyyy HH:mm:ss"));
          found = true;
          break;
        }
      }

      return ContentService.createTextOutput(JSON.stringify({ success: true, found: found, message: "Status atualizado para confirmado!" }))
        .setMimeType(ContentService.MimeType.JSON);
    }

    // 3. CANCELAMENTO DE RESERVA
    if (action === "cancel_order") {
      var values = sheet.getDataRange().getValues();
      var found = false;

      for (var i = 1; i < values.length; i++) {
        if (String(values[i][0]) === String(data.order_id)) {
          var rowIndex = i + 1;
          var statusCell = sheet.getRange(rowIndex, 9);
          statusCell.setValue("cancelado").setBackground("#fee2e2").setFontColor("#991b1b").setFontWeight("bold");
          var currentObs = values[i][11] ? String(values[i][11]) + " | " : "";
          sheet.getRange(rowIndex, 12).setValue(currentObs + "[Cancelado: " + (data.reason || "Líder") + "]");
          found = true;
          break;
        }
      }

      return ContentService.createTextOutput(JSON.stringify({ success: true, found: found, message: "Status atualizado para cancelado!" }))
        .setMimeType(ContentService.MimeType.JSON);
    }

    return ContentService.createTextOutput(JSON.stringify({ success: false, error: "Ação desconhecida" }))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ success: false, error: err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

// -------------------------------------------------------------------------
// GET: O site consulta a planilha ao inicializar para restaurar os dados!
// -------------------------------------------------------------------------
function doGet(e) {
  try {
    var sheet = getOrCreateSheet();
    var values = sheet.getDataRange().getValues();

    if (values.length <= 1) {
      return ContentService.createTextOutput(JSON.stringify({ success: true, count: 0, orders: [] }))
        .setMimeType(ContentService.MimeType.JSON);
    }

    var orders = [];
    for (var i = 1; i < values.length; i++) {
      var row = values[i];
      var orderId = row[0];
      if (!orderId) continue;

      // Extrai os números do bilhete
      var numString = String(row[5] || "");
      var numbers = numString.split(",")
        .map(function(s) { return parseInt(s.trim(), 10); })
        .filter(function(n) { return !isNaN(n) && n > 0; });

      orders.push({
        order_id: parseInt(orderId, 10),
        created_at: String(row[1] || ""),
        buyer_name: String(row[2] || ""),
        buyer_phone: String(row[3] || "").replace(/^'/, ""),
        seller_name: String(row[4] || ""),
        numbers: numbers,
        total_tickets: parseInt(row[6], 10) || numbers.length,
        total_amount: parseFloat(row[7]) || 0,
        status: String(row[8] || "pendente").toLowerCase().trim(),
        confirmed_by: String(row[9] || ""),
        confirmed_at: String(row[10] || ""),
        notes: String(row[11] || "")
      });
    }

    return ContentService.createTextOutput(JSON.stringify({ success: true, count: orders.length, orders: orders }))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ success: false, error: err.toString(), orders: [] }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}
