package com.trip.infra;

import java.util.Locale;

import org.springframework.stereotype.Component;

import com.fasterxml.jackson.databind.JsonNode;
import com.trip.domain.Budget;

/**
 * 服务端渲染导出的 HTML（浏览器可另存/直接打印为 PDF）。
 * 相比前端 html2canvas，服务端渲染不受 Canvas 限制。
 */
@Component
public class ExportRenderer {

    public String render(JsonNode plan, Budget budget) {
        StringBuilder html = new StringBuilder(4096);
        html.append("<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">")
                .append("<title>").append(esc(plan.path("city").asText())).append(" 行程</title>")
                .append("<style>")
                .append("body{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;background:#f6f7fb;color:#1f2937;margin:0;padding:40px}")
                .append(".page{max-width:900px;margin:0 auto;background:#fff;border-radius:16px;padding:40px;box-shadow:0 8px 30px rgba(15,23,42,.08)}")
                .append("h1{margin:0 0 8px;font-size:28px}.meta{color:#6b7280;margin-bottom:24px}")
                .append(".summary{background:#f3f6ff;border-left:4px solid #4f6ef7;padding:14px 18px;border-radius:8px;line-height:1.7}")
                .append(".day{margin-top:28px;border-top:1px solid #e5e7eb;padding-top:20px}")
                .append(".day h2{font-size:18px;margin:0 0 6px}.theme{color:#4f6ef7;font-size:14px;margin-bottom:12px}")
                .append(".item{padding:10px 0;border-bottom:1px dashed #eef0f4;line-height:1.6}")
                .append(".item b{font-size:15px}.muted{color:#6b7280;font-size:13px}")
                .append(".budget{margin-top:28px;background:#0f172a;color:#e5e7eb;border-radius:12px;padding:20px}")
                .append(".budget table{width:100%;border-collapse:collapse;font-size:14px}")
                .append(".budget td{padding:6px 0}.budget .total{font-size:20px;font-weight:700;color:#fff}")
                .append("</style></head><body><div class=\"page\">")
                .append("<h1>").append(esc(plan.path("city").asText())).append(" 行程计划</h1>")
                .append("<div class=\"meta\">").append(esc(plan.path("start_date").asText()))
                .append(" ~ ").append(esc(plan.path("end_date").asText()))
                .append(" · 单人预算 · 由智能旅行助手生成</div>")
                .append("<div class=\"summary\">").append(esc(plan.path("summary").asText())).append("</div>");

        for (JsonNode day : plan.path("days")) {
            html.append("<div class=\"day\"><h2>").append(esc(day.path("theme").asText("行程"))).append("</h2>")
                    .append("<div class=\"theme\">").append(esc(day.path("date").asText())).append("</div>");
            for (JsonNode attraction : day.path("attractions")) {
                html.append("<div class=\"item\"><b>").append(esc(attraction.path("name").asText()))
                        .append("</b><div class=\"muted\">").append(esc(attraction.path("address").asText()))
                        .append(" · ").append(esc(attraction.path("visit_duration").asText()))
                        .append(" · 门票 ").append(yuan(attraction.path("ticket_price").asDouble()))
                        .append("</div><div>").append(esc(attraction.path("description").asText())).append("</div></div>");
            }
            for (JsonNode meal : day.path("meals")) {
                html.append("<div class=\"item\">").append(esc(meal.path("type").asText()))
                        .append("：").append(esc(meal.path("name").asText()))
                        .append(" <span class=\"muted\">").append(yuan(meal.path("estimated_cost").asDouble()))
                        .append("</span></div>");
            }
            JsonNode hotel = day.path("hotel");
            if (hotel.isObject()) {
                html.append("<div class=\"item\">住宿：").append(esc(hotel.path("name").asText()))
                        .append(" <span class=\"muted\">").append(yuan(hotel.path("price_per_night").asDouble()))
                        .append("/晚</span></div>");
            }
            html.append("</div>");
        }

        html.append("<div class=\"budget\"><table>")
                .append(row("景点门票", budget.attractionsCents()))
                .append(row("住宿", budget.hotelsCents()))
                .append(row("餐饮", budget.mealsCents()))
                .append(row("市内交通", budget.transportCents()))
                .append("<tr><td class=\"total\">合计</td><td class=\"total\" style=\"text-align:right\">")
                .append(yuanCents(budget.totalCents())).append("</td></tr>")
                .append("</table><div class=\"muted\" style=\"margin-top:10px;color:#94a3b8\">")
                .append(esc(budget.unit())).append("估算，不含往返大交通</div></div>")
                .append("</div></body></html>");
        return html.toString();
    }

    private static String row(String label, long cents) {
        return "<tr><td>" + label + "</td><td style=\"text-align:right\">" + yuanCents(cents) + "</td></tr>";
    }

    private static String yuan(double value) {
        return String.format(Locale.CHINA, "¥%.0f", value);
    }

    private static String yuanCents(long cents) {
        return String.format(Locale.CHINA, "¥%.2f", cents / 100.0);
    }

    private static String esc(String value) {
        if (value == null) {
            return "";
        }
        return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                .replace("\"", "&quot;");
    }
}
