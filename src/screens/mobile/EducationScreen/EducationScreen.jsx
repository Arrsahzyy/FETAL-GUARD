import React, { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../../context/useAuth";
import {
  EDUCATION_REFERENCE_CHECKED_AT,
  getEducationArticles,
  getWeeklyEducationArticle,
} from "../../../content/patientEducation";
import { t } from "../../../i18n";
import { useI18n } from "../../../i18n/useI18n";
import Icon from "../../../components/Icon/Icon";
import "./EducationScreen.css";

const formatReferenceDate = (date, locale) => new Intl.DateTimeFormat(
  locale === "en" ? "en-US" : "id-ID",
  { day: "numeric", month: "long", year: "numeric" },
).format(new Date(`${date}T00:00:00`));

const EducationArticle = ({ article, expanded, featured = false, onToggle }) => {
  const detailId = `education-${article.id}-detail`;

  return (
    <article
      id={`education-${article.id}`}
      className={`education-card education-card--${article.tone}${featured ? " education-card--featured" : ""}${expanded ? " education-card--expanded" : ""}`}
    >
      <button
        type="button"
        className="education-card__trigger"
        onClick={onToggle}
        aria-expanded={expanded}
        aria-controls={detailId}
      >
        <Icon className="education-card__icon material-symbols-outlined" name={article.icon} />
        <span className="education-card__heading-copy">
          <span className="education-card__source-type">
            {featured
              ? t("patient.education.officialSource")
              : t("patient.education.quickRead")}
          </span>
          <span className="education-card__title">{article.title}</span>
          {featured && <span className="education-card__summary">{article.summary}</span>}
        </span>
        <span className="education-card__toggle-label">
          {expanded
            ? t("patient.education.hideDetails")
            : t("patient.education.openTopic")}
          <Icon
            className="material-symbols-outlined"
            name="expand_more"
            aria-hidden="true"
          />
        </span>
      </button>

      {expanded && (
        <div className="education-card__details" id={detailId}>
          {!featured && <p className="education-card__summary">{article.summary}</p>}

          <dl className="education-card__guidance">
            <div>
              <dt>
                <Icon className="material-symbols-outlined" name="check_circle" />
                {t("patient.education.actionLabel")}
              </dt>
              <dd>{article.action}</dd>
            </div>
            <div>
              <dt>
                <Icon className="material-symbols-outlined" name="do_not_disturb_on" />
                {t("patient.education.cautionLabel")}
              </dt>
              <dd>{article.caution}</dd>
            </div>
            <div className="education-card__urgent">
              <dt>
                <Icon className="material-symbols-outlined" name="health_and_safety" />
                {t("patient.education.urgentLabel")}
              </dt>
              <dd>{article.urgent}</dd>
            </div>
          </dl>

          <details className="education-card__sources">
            <summary>
              <Icon className="material-symbols-outlined" name="verified" />
              {t("patient.education.sourceCount", { count: article.sources.length })}
            </summary>
            <ul>
              {article.sources.map((source) => (
                <li key={source.url}>
                  <a href={source.url} target="_blank" rel="noreferrer">
                    {source.organization}: {source.title}
                    <Icon className="material-symbols-outlined" name="open_in_new" />
                  </a>
                </li>
              ))}
            </ul>
          </details>
        </div>
      )}
    </article>
  );
};

const EducationScreen = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { locale } = useI18n();
  const [expandedArticleId, setExpandedArticleId] = useState(null);
  const pregnancyWeek = Number(user?.patientProfile?.gestational_age_weeks);
  const hasPregnancyWeek = Number.isFinite(pregnancyWeek)
    && pregnancyWeek >= 1
    && pregnancyWeek <= 42;
  const articles = useMemo(() => getEducationArticles(locale), [locale]);
  const weeklyArticle = useMemo(
    () => getWeeklyEducationArticle(pregnancyWeek, locale),
    [locale, pregnancyWeek],
  );
  const otherArticles = articles.filter((article) => article.id !== weeklyArticle.id);
  const referenceDate = formatReferenceDate(EDUCATION_REFERENCE_CHECKED_AT, locale);

  const openHelpOptions = () => {
    window.dispatchEvent(new CustomEvent("fetalguard:open-emergency"));
  };

  const toggleArticle = (articleId) => {
    setExpandedArticleId((currentId) => (
      currentId === articleId ? null : articleId
    ));
  };

  return (
    <div className="education-screen">
      <header className="education-header">
        <button
          type="button"
          className="education-header__back"
          onClick={() => navigate("/patient/home")}
          aria-label={t("patient.education.backAria")}
        >
          <Icon className="material-symbols-outlined" name="arrow_back" />
        </button>
        <div>
          <h1>{t("patient.education.title")}</h1>
          <p>{t("patient.education.subtitle")}</p>
        </div>
      </header>

      <div className="education-content">
        <section className="education-intro" aria-labelledby="education-weekly-title">
          <div>
            <span className="education-intro__eyebrow">
              {hasPregnancyWeek
                ? t("patient.education.weekLabel", { week: Math.round(pregnancyWeek) })
                : t("patient.education.generalLabel")}
            </span>
            <h2 id="education-weekly-title">{t("patient.education.weeklyTitle")}</h2>
          </div>
          <span className="education-intro__review">
            <Icon className="material-symbols-outlined" name="verified" />
            {t("patient.education.referenceChecked", { date: referenceDate })}
          </span>
        </section>

        <EducationArticle
          article={weeklyArticle}
          expanded={expandedArticleId === weeklyArticle.id}
          featured
          onToggle={() => toggleArticle(weeklyArticle.id)}
        />

        <section className="education-help" aria-labelledby="education-help-title">
          <Icon className="education-help__icon material-symbols-outlined" name="emergency" />
          <div>
            <h2 id="education-help-title">{t("patient.education.safetyTitle")}</h2>
            <p>{t("patient.education.safetyDesc")}</p>
          </div>
          <button type="button" onClick={openHelpOptions}>
            {t("patient.education.openHelp")}
          </button>
        </section>

        <section className="education-topics" aria-labelledby="education-topics-title">
          <div className="education-section-heading">
            <Icon className="material-symbols-outlined" name="menu_book" />
            <div>
              <h2 id="education-topics-title">{t("patient.education.allTopics")}</h2>
              <p>{t("patient.education.topicHint")}</p>
            </div>
          </div>
          <div className="education-topic-list">
            {otherArticles.map((article) => (
              <EducationArticle
                key={article.id}
                article={article}
                expanded={expandedArticleId === article.id}
                onToggle={() => toggleArticle(article.id)}
              />
            ))}
          </div>
        </section>

        <aside className="education-source-note" role="note">
          <Icon className="material-symbols-outlined" name="clinical_notes" />
          <p>{t("patient.education.sourceNote")}</p>
        </aside>
      </div>
    </div>
  );
};

export default EducationScreen;
