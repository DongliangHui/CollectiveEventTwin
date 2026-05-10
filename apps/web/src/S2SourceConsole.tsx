import { Database, FileText, Gauge, KeyRound, ListFilter, Pause, Play, RefreshCw, RotateCcw, ShieldAlert } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type { ChannelErrorMapping, DataSourceRecord, JsonMap } from "./api";

type LineTone = "empty" | "error" | "loading";

const CLEAN_RECORD_STATUSES = ["raw", "cleaned", "valid", "invalid", "review_required", "dedupe_candidate", "confirmed_duplicate", "duplicate", "kept", "split_candidate", "embedding_failed", "pending", "failed", "quarantined"];

export function S2SourceConsole() {
  const queryClient = useQueryClient();
  const [sourceName, setSourceName] = useState("Xian synthetic governance source");
  const [sourceType, setSourceType] = useState("synthetic");
  const [filterType, setFilterType] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [sourcePage, setSourcePage] = useState(1);
  const [jobStatusFilter, setJobStatusFilter] = useState("");
  const [jobSourceFilter, setJobSourceFilter] = useState("");
  const [jobCreatorFilter, setJobCreatorFilter] = useState("");
  const [jobPage, setJobPage] = useState(1);
  const [selectedJobId, setSelectedJobId] = useState("");
  const [selectedRunId, setSelectedRunId] = useState("");
  const [runStatusFilter, setRunStatusFilter] = useState("");
  const [runSourceFilter, setRunSourceFilter] = useState("");
  const [runJobFilter, setRunJobFilter] = useState("");
  const [runCreatedFromFilter, setRunCreatedFromFilter] = useState("");
  const [runCreatedToFilter, setRunCreatedToFilter] = useState("");
  const [runPage, setRunPage] = useState(1);
  const [cleanStatusFilter, setCleanStatusFilter] = useState("");
  const [cleanSourceFilter, setCleanSourceFilter] = useState("");
  const [cleanTypeFilter, setCleanTypeFilter] = useState("");
  const [cleanCreatedFromFilter, setCleanCreatedFromFilter] = useState("");
  const [cleanCreatedToFilter, setCleanCreatedToFilter] = useState("");
  const [cleanPage, setCleanPage] = useState(1);
  const [selectedCleanRecordId, setSelectedCleanRecordId] = useState("");
  const [qualityIssueTypeFilter, setQualityIssueTypeFilter] = useState("");
  const [qualityIssueSeverityFilter, setQualityIssueSeverityFilter] = useState("");
  const [qualityIssuePage, setQualityIssuePage] = useState(1);
  const [publicWebUrl, setPublicWebUrl] = useState("synthetic://xian/public-notice");
  const [crawlDepth, setCrawlDepth] = useState(2);
  const [officialApiBaseUrl, setOfficialApiBaseUrl] = useState("synthetic://xian/official-api");
  const [officialApiSecretRef, setOfficialApiSecretRef] = useState("vault://s2/xian-official-api");
  const [officialApiSamplePath, setOfficialApiSamplePath] = useState("/xian/issues");
  const [officialApiMaxPages, setOfficialApiMaxPages] = useState(3);
  const [rssFeedUrl, setRssFeedUrl] = useState("synthetic://xian/rss-social-issues");
  const [webhookSourceKey, setWebhookSourceKey] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");
  const [webhookEndpoint, setWebhookEndpoint] = useState("");
  const [lastLineageRawId, setLastLineageRawId] = useState("");
  const [selectedHealthSourceId, setSelectedHealthSourceId] = useState("");
  const [selectedUploadFile, setSelectedUploadFile] = useState<File | null>(null);
  const [manualTitle, setManualTitle] = useState("Xi'an pension queue field note");
  const [manualContent, setManualContent] = useState("synthetic manual entry: Xi'an pension insurance service queue update from a resident call-in, with backend masking verification enabled.");
  const [manualOccurredAt, setManualOccurredAt] = useState("2026-05-09T09:30:00Z");
  const [manualLocation, setManualLocation] = useState("Beilin government service hall");
  const [manualIsSynthetic, setManualIsSynthetic] = useState(true);
  const [dbImportTableName, setDbImportTableName] = useState("public_petition_rows");
  const [dbImportLimit, setDbImportLimit] = useState(1000);
  const [objectStoragePrefix, setObjectStoragePrefix] = useState("synthetic/public-service/");
  const [objectStorageScanLimit, setObjectStorageScanLimit] = useState(1000);
  const [rateLimitSourceId, setRateLimitSourceId] = useState("");
  const [rateLimitJobIds, setRateLimitJobIds] = useState<string[]>([]);

  const permissions = useQuery({ queryKey: ["s1-permissions"], queryFn: api.permissions });
  const types = useQuery({ queryKey: ["s2-source-types"], queryFn: api.listDataSourceTypes });
  const collectionChannels = useQuery({ queryKey: ["s2-collection-channels"], queryFn: api.listCollectionChannels });
  const adapterContract = useQuery({ queryKey: ["s2-channel-adapter-contract"], queryFn: api.validateChannelAdapterContract });
  const channelErrorCodes = useQuery({ queryKey: ["s2-channel-error-codes"], queryFn: () => api.mapCollectionChannelErrorCodes() });
  const webPageQualityMetrics = useQuery({ queryKey: ["s2-channel-quality", "web_page"], queryFn: () => api.getCollectionChannelQualityMetrics("web_page") });
  const rssQualityMetrics = useQuery({ queryKey: ["s2-channel-quality", "rss"], queryFn: () => api.getCollectionChannelQualityMetrics("rss") });
  const channelMaintenance = useQuery({ queryKey: ["s2-channel-maintenance"], queryFn: api.getCollectionChannelMaintenance });
  const webPageChannelSchema = useQuery({ queryKey: ["s2-channel-schema", "web_page"], queryFn: () => api.getCollectionChannelSchema("web_page") });
  const officialApiChannelSchema = useQuery({ queryKey: ["s2-channel-schema", "official_api"], queryFn: () => api.getCollectionChannelSchema("official_api") });
  const documentFileChannelSchema = useQuery({ queryKey: ["s2-channel-schema", "document_file"], queryFn: () => api.getCollectionChannelSchema("document_file") });
  const imageFileChannelSchema = useQuery({ queryKey: ["s2-channel-schema", "image_file"], queryFn: () => api.getCollectionChannelSchema("image_file") });
  const videoFileChannelSchema = useQuery({ queryKey: ["s2-channel-schema", "video_file"], queryFn: () => api.getCollectionChannelSchema("video_file") });
  const livestreamChannelSchema = useQuery({ queryKey: ["s2-channel-schema", "livestream"], queryFn: () => api.getCollectionChannelSchema("livestream") });
  const audioFileChannelSchema = useQuery({ queryKey: ["s2-channel-schema", "audio_file"], queryFn: () => api.getCollectionChannelSchema("audio_file") });
  const adapterCapabilities = useQuery({ queryKey: ["s2-adapter-capabilities"], queryFn: () => api.listAdapterCapabilities() });
  const sources = useQuery({
    queryKey: ["s2-data-sources", filterType, filterStatus, sourcePage],
    queryFn: () => api.listDataSources({ sourceType: filterType || undefined, status: filterStatus || undefined, page: sourcePage, pageSize: 8 })
  });
  const collectionJobs = useQuery({
    queryKey: ["s2-collection-jobs", jobStatusFilter, jobSourceFilter, jobCreatorFilter, jobPage],
    queryFn: () =>
      api.listCollectionJobs({
        status: jobStatusFilter || undefined,
        dataSourceId: jobSourceFilter || undefined,
        createdById: jobCreatorFilter || undefined,
        page: jobPage,
        pageSize: 8
      })
  });
  const collectionJobDetail = useQuery({
    queryKey: ["s2-collection-job-detail", selectedJobId],
    enabled: Boolean(selectedJobId),
    queryFn: () => api.getCollectionJob(selectedJobId)
  });
  const collectionRuns = useQuery({
    queryKey: ["s2-collection-runs", runStatusFilter, runSourceFilter, runJobFilter, runCreatedFromFilter, runCreatedToFilter, runPage],
    queryFn: () =>
      api.listCollectionRuns({
        status: runStatusFilter || undefined,
        dataSourceId: runSourceFilter || undefined,
        collectionJobId: runJobFilter || undefined,
        createdFrom: runCreatedFromFilter || undefined,
        createdTo: runCreatedToFilter || undefined,
        page: runPage,
        pageSize: 8
      })
  });
  const collectionRunSteps = useQuery({
    queryKey: ["s2-collection-run-steps", selectedRunId],
    enabled: Boolean(selectedRunId),
    queryFn: () => api.getCollectionRunSteps(selectedRunId),
    refetchInterval: selectedRunId ? 5000 : false
  });
  const collectionRunMetrics = useQuery({
    queryKey: ["s2-cleaning-run-metrics", selectedRunId],
    enabled: Boolean(selectedRunId),
    queryFn: () => api.getCleaningRunMetrics(selectedRunId)
  });
  const health = useQuery({ queryKey: ["s2-source-health"], queryFn: api.sourceHealthView });
  const healthDetail = useQuery({
    queryKey: ["s2-source-health-detail", selectedHealthSourceId],
    enabled: Boolean(selectedHealthSourceId),
    queryFn: () => api.getDataSourceHealth(selectedHealthSourceId)
  });
  const rateLimitStats = useQuery({
    queryKey: ["s2-source-rate-limit", rateLimitSourceId],
    enabled: Boolean(rateLimitSourceId),
    queryFn: () => api.getDataSourceRateLimit(rateLimitSourceId)
  });
  const rawRecords = useQuery({ queryKey: ["s2-raw-records"], queryFn: api.listRawRecords });
  const cleanRecords = useQuery({
    queryKey: ["s2-clean-records", cleanStatusFilter, cleanSourceFilter, cleanTypeFilter, cleanCreatedFromFilter, cleanCreatedToFilter, cleanPage],
    queryFn: () =>
      api.listCleanRecords({
        status: cleanStatusFilter || undefined,
        dataSourceId: cleanSourceFilter || undefined,
        sourceType: cleanTypeFilter || undefined,
        createdFrom: cleanCreatedFromFilter || undefined,
        createdTo: cleanCreatedToFilter || undefined,
        page: cleanPage,
        pageSize: 8
      })
  });
  const cleanRecordDetail = useQuery({
    queryKey: ["s2-clean-record-detail", selectedCleanRecordId],
    enabled: Boolean(selectedCleanRecordId),
    queryFn: () => api.getCleanRecord(selectedCleanRecordId)
  });
  const importRuns = useQuery({ queryKey: ["s2-import-runs"], queryFn: api.listImportRuns });
  const deadLetters = useQuery({ queryKey: ["s2-dead-letters"], queryFn: () => api.listDeadLetters({ pageSize: 8 }) });
  const normalizationRuns = useQuery({ queryKey: ["s2-normalization-runs"], queryFn: api.listNormalizationRuns });
  const deduplicationRuns = useQuery({ queryKey: ["s2-deduplication-runs"], queryFn: api.listDeduplicationRuns });
  const qualityRuns = useQuery({ queryKey: ["s2-quality-runs"], queryFn: api.listDataQualityRuns });
  const qualityIssues = useQuery({
    queryKey: ["s2-quality-issues", qualityIssueTypeFilter, qualityIssueSeverityFilter, qualityIssuePage],
    queryFn: () =>
      api.listDataQualityIssues({
        issueType: qualityIssueTypeFilter || undefined,
        severity: qualityIssueSeverityFilter || undefined,
        page: qualityIssuePage,
        pageSize: 8
      })
  });
  const lineage = useQuery({
    queryKey: ["s2-lineage", lastLineageRawId],
    enabled: Boolean(lastLineageRawId),
    queryFn: () => api.getLineage("raw_record", lastLineageRawId)
  });
  const rawDetail = useQuery({
    queryKey: ["s2-raw-detail", lastLineageRawId],
    enabled: Boolean(lastLineageRawId),
    queryFn: () => api.getRawRecord(lastLineageRawId)
  });

  const refreshAll = async () => {
    await queryClient.invalidateQueries({ queryKey: ["s2-source-types"] });
    await queryClient.invalidateQueries({ queryKey: ["s2-collection-channels"] });
    await queryClient.invalidateQueries({ queryKey: ["s2-channel-adapter-contract"] });
    await queryClient.invalidateQueries({ queryKey: ["s2-channel-error-codes"] });
    await queryClient.invalidateQueries({ queryKey: ["s2-channel-quality"] });
    await queryClient.invalidateQueries({ queryKey: ["s2-channel-maintenance"] });
    await queryClient.invalidateQueries({ queryKey: ["s2-channel-schema", "web_page"] });
    await queryClient.invalidateQueries({ queryKey: ["s2-channel-schema", "official_api"] });
    await queryClient.invalidateQueries({ queryKey: ["s2-channel-schema", "document_file"] });
    await queryClient.invalidateQueries({ queryKey: ["s2-channel-schema", "image_file"] });
    await queryClient.invalidateQueries({ queryKey: ["s2-channel-schema", "video_file"] });
    await queryClient.invalidateQueries({ queryKey: ["s2-channel-schema", "livestream"] });
    await queryClient.invalidateQueries({ queryKey: ["s2-channel-schema", "audio_file"] });
    await queryClient.invalidateQueries({ queryKey: ["s2-adapter-capabilities"] });
    await queryClient.invalidateQueries({ queryKey: ["s2-data-sources"] });
    await queryClient.invalidateQueries({ queryKey: ["s2-collection-jobs"] });
    await queryClient.invalidateQueries({ queryKey: ["s2-collection-job-detail"] });
    await queryClient.invalidateQueries({ queryKey: ["s2-collection-runs"] });
    await queryClient.invalidateQueries({ queryKey: ["s2-collection-run-steps"] });
    await queryClient.invalidateQueries({ queryKey: ["s2-cleaning-run-metrics"] });
    await queryClient.invalidateQueries({ queryKey: ["s2-source-health"] });
    await queryClient.invalidateQueries({ queryKey: ["s2-source-health-detail"] });
    await queryClient.invalidateQueries({ queryKey: ["s2-source-rate-limit"] });
    await queryClient.invalidateQueries({ queryKey: ["s2-raw-records"] });
    await queryClient.invalidateQueries({ queryKey: ["s2-clean-records"] });
    await queryClient.invalidateQueries({ queryKey: ["s2-clean-record-detail"] });
    await queryClient.invalidateQueries({ queryKey: ["s2-import-runs"] });
    await queryClient.invalidateQueries({ queryKey: ["s2-dead-letters"] });
    await queryClient.invalidateQueries({ queryKey: ["s2-normalization-runs"] });
    await queryClient.invalidateQueries({ queryKey: ["s2-deduplication-runs"] });
    await queryClient.invalidateQueries({ queryKey: ["s2-quality-runs"] });
    await queryClient.invalidateQueries({ queryKey: ["s2-quality-issues"] });
    await queryClient.invalidateQueries({ queryKey: ["s2-lineage"] });
    await queryClient.invalidateQueries({ queryKey: ["s2-raw-detail"] });
  };

  const canRead = permissions.isLoading || Boolean(permissions.data?.data.permissions.includes("data_source:read"));
  const canWrite = Boolean(permissions.data?.data.permissions.includes("data_source:write"));

  const createSource = useMutation({
    mutationFn: () =>
      api.createDataSource(sourceName, sourceType, {
        access_mode: sourceType === "synthetic" ? "test_fixture" : sourceType === "public_web" ? "public_web" : undefined
      }),
    onSuccess: refreshAll
  });
  const createBlocked = useMutation({
    mutationFn: () => api.createDataSource("Blocked cookie-pool source", "public_web", { access_mode: "cookie_pool" }),
    onSuccess: refreshAll
  });
  const policyCheck = useMutation({
    mutationFn: (dataSourceId: string) => api.checkDataSourcePolicy(dataSourceId),
    onSuccess: refreshAll
  });
  const disableSource = useMutation({
    mutationFn: (dataSourceId: string) => api.updateDataSourceStatus(dataSourceId, "disabled", "AT-051 frontend source disable"),
    onSuccess: refreshAll
  });
  const enableSource = useMutation({
    mutationFn: (dataSourceId: string) => api.updateDataSourceStatus(dataSourceId, "active", "AT-051 frontend source re-enable"),
    onSuccess: refreshAll
  });
  const validateUrl = useMutation({
    mutationFn: async () => api.validateDataSourceUrl(await ensureSourceId("public_web", "S2 public web validation source", { access_mode: "public_web", base_url: publicWebUrl }), publicWebUrl),
    onSuccess: refreshAll
  });
  const saveCrawlPolicy = useMutation({
    mutationFn: async () =>
      api.updateDataSourceCrawlPolicy(await ensureSourceId("public_web", "S2 public web validation source", { access_mode: "public_web", base_url: publicWebUrl }), {
        start_url: publicWebUrl,
        max_depth: crawlDepth,
        respect_robots: true,
        rate_limit_per_minute: 30,
        reason: "S2 public web crawl policy saved from source console."
      }),
    onSuccess: refreshAll
  });
  const discoverLinks = useMutation({
    mutationFn: async () =>
      api.discoverPublicWebLinks(await ensureSourceId("public_web", "S2 public web validation source", { access_mode: "public_web", base_url: publicWebUrl }), {
        start_url: publicWebUrl,
        max_depth: crawlDepth,
        limit: 1000,
        respect_robots: true,
        reason: "AT-068 public web link discovery from source console."
      }),
    onSuccess: refreshAll
  });
  const createOfficialApi = useMutation({
    mutationFn: async () => {
      const dataSourceId = await ensureOfficialApiSourceId();
      const current = await api.listDataSources({ sourceType: "official_api", pageSize: 50 });
      const source = current.data.find((item) => item.data_source_id === dataSourceId);
      if (!source) throw new Error("Official API source was not returned by backend.");
      return source;
    },
    onSuccess: refreshAll
  });
  const saveOfficialAuth = useMutation({
    mutationFn: async () =>
      api.updateDataSourceAuth(await ensureOfficialApiSourceId(), {
        auth_type: "api_key",
        secret_ref: officialApiSecretRef,
        header_name: "X-API-Key",
        reason: "S2 official_api secret_ref saved from source console."
      }),
    onSuccess: refreshAll
  });
  const testOfficialConnection = useMutation({
    mutationFn: async () => api.testDataSourceConnection(await ensureOfficialApiSourceId(), { sample_path: officialApiSamplePath, expected_status: 200 }),
    onSuccess: refreshAll
  });
  const saveOfficialCompliance = useMutation({
    mutationFn: async () =>
      api.updateDataSourceCompliance(await ensureOfficialApiSourceId(), {
        authorization_scope: "public_sector_notice",
        authorization_basis: "Xi'an first-phase public notice synthetic adapter; no private-domain data.",
        retention_days: 180,
        data_classification: "public",
        pii_policy: "masked",
        synthetic_allowed: true,
        reason: "AT-053 frontend compliance tags saved before publication."
      }),
    onSuccess: refreshAll
  });
  const publishOfficialVersion = useMutation({
    mutationFn: async () => api.publishDataSourceVersion(await ensureOfficialApiSourceId(), "AT-049 frontend source version publish"),
    onSuccess: refreshAll
  });
  const rollbackOfficialVersion = useMutation({
    mutationFn: async () => api.rollbackDataSourceVersion(await ensureOfficialApiSourceId(), 1, "AT-050 frontend source version rollback"),
    onSuccess: refreshAll
  });
  const createOnceJob = useMutation({
    mutationFn: async () =>
      api.createCollectionJob(await ensureOfficialApiSourceId(), `S2 once collection ${Date.now()}`, "once", {
        query: { district: "雁塔区", topic: "public service" },
        window: { from: "2026-05-01", to: "2026-05-09" }
      }),
    onSuccess: refreshAll
  });
  const createCronJob = useMutation({
    mutationFn: async () =>
      api.createCollectionJob(await ensureOfficialApiSourceId(), `S2 cron collection ${Date.now()}`, "cron:*/15 * * * *", {
        query: { district: "yanta", topic: "public service" },
        window: { from: "2026-05-01", to: "2026-05-09" }
      }),
    onSuccess: refreshAll
  });
  const startJobRun = useMutation({
    mutationFn: async (collectionJobId: string) => api.startCollectionRun(collectionJobId),
    onSuccess: async (_data, collectionJobId) => {
      setSelectedJobId(collectionJobId);
      await refreshAll();
    }
  });
  const pauseJob = useMutation({
    mutationFn: async (collectionJobId: string) => api.pauseCollectionJob(collectionJobId, "AT-061 frontend pause collection job"),
    onSuccess: async (_data, collectionJobId) => {
      setSelectedJobId(collectionJobId);
      setJobStatusFilter("paused");
      setJobPage(1);
      await refreshAll();
    }
  });
  const resumeJob = useMutation({
    mutationFn: async (collectionJobId: string) => api.resumeCollectionJob(collectionJobId, "AT-062 frontend resume collection job"),
    onSuccess: async (_data, collectionJobId) => {
      setSelectedJobId(collectionJobId);
      setJobStatusFilter("active");
      setJobPage(1);
      await refreshAll();
    }
  });
  const cancelRun = useMutation({
    mutationFn: async (collectionRunId: string) => api.cancelCollectionRun(collectionRunId),
    onSuccess: refreshAll
  });
  const retryRun = useMutation({
    mutationFn: async (collectionRunId: string) => api.retryCollectionRun(collectionRunId),
    onSuccess: refreshAll
  });
  const replayChannelCheckpoint = useMutation({
    mutationFn: async () => {
      const dataSourceId = await ensureOfficialApiSourceId();
      await api.updateDataSourceAuth(dataSourceId, {
        auth_type: "api_key",
        secret_ref: officialApiSecretRef,
        header_name: "X-API-Key",
        reason: "AT-304 frontend channel replay checkpoint auth."
      });
      await api.updateDataSourcePagination(dataSourceId, {
        strategy: "page",
        page_param: "page",
        page_size_param: "limit",
        max_pages: officialApiMaxPages,
        dry_run: true,
        reason: "AT-304 frontend channel replay checkpoint pagination."
      });
      const failed = await api.fetchOfficialApi(dataSourceId, 2, "synthetic://xian/official-api/500");
      const failedRunId = stringValue(mapValue(failed.data.collection_run)?.collection_run_id);
      if (!failedRunId) throw new Error("Official API checkpoint failure did not return a collection run.");
      const replay = await api.replayCollectionRunFromCheckpoint(failedRunId, {
        reason: "AT-304 frontend replay from channel checkpoint.",
        payload: { source: "S2SourceConsole", collection_channel: "official_api" }
      });
      return { failed: failed.data, replay: replay.data, dataSourceId };
    },
    onSuccess: async (result) => {
      const replayRunId = stringValue(result.replay.collection_run_id);
      const replayJobId = stringValue(result.replay.collection_job_id);
      if (replayRunId) setSelectedRunId(replayRunId);
      if (replayJobId) setSelectedJobId(replayJobId);
      setRunSourceFilter(result.dataSourceId);
      setRunStatusFilter("pending");
      setRunPage(1);
      await refreshAll();
    }
  });
  const createRateLimitJobs = useMutation({
    mutationFn: createRateLimitJobPair,
    onSuccess: async (result) => {
      setRateLimitSourceId(result.dataSourceId);
      setRateLimitJobIds(result.jobIds);
      setJobSourceFilter(result.dataSourceId);
      setJobPage(1);
      await refreshAll();
      await queryClient.invalidateQueries({ queryKey: ["s2-source-rate-limit", result.dataSourceId] });
    }
  });
  const runRateLimitTwice = useMutation({
    mutationFn: async () => {
      const created = await createRateLimitJobPair();
      const first = await api.startCollectionRun(created.webJobIds[0]);
      const second = await api.startCollectionRun(created.webJobIds[1]);
      const rss = await api.startCollectionRun(created.rssJobId);
      const stats = await api.getDataSourceRateLimit(created.dataSourceId, "web_page");
      const rssStats = await api.getDataSourceRateLimit(created.dataSourceId, "rss");
      const aggregateStats = await api.getDataSourceRateLimit(created.dataSourceId);
      return { ...created, first: first.data, second: second.data, rss: rss.data, stats: stats.data, rssStats: rssStats.data, aggregateStats: aggregateStats.data };
    },
    onSuccess: async (result) => {
      setRateLimitSourceId(result.dataSourceId);
      setRateLimitJobIds(result.jobIds);
      setSelectedJobId(result.jobIds[1]);
      const delayedRunId = stringValue(result.second.collection_run_id);
      if (delayedRunId) setSelectedRunId(delayedRunId);
      setRunSourceFilter(result.dataSourceId);
      setRunStatusFilter("delayed");
      setRunPage(1);
      await refreshAll();
      await queryClient.invalidateQueries({ queryKey: ["s2-source-rate-limit", result.dataSourceId] });
    }
  });
  const loadRateLimitStats = useMutation({
    mutationFn: async () => {
      const sourceId = rateLimitSourceId || (await createRateLimitJobPair()).dataSourceId;
      setRateLimitSourceId(sourceId);
      return api.getDataSourceRateLimit(sourceId);
    },
    onSuccess: refreshAll
  });
  const saveOfficialPagination = useMutation({
    mutationFn: async () =>
      api.updateDataSourcePagination(await ensureOfficialApiSourceId(), {
        strategy: "page",
        page_param: "page",
        page_size_param: "limit",
        max_pages: officialApiMaxPages,
        dry_run: true,
        reason: "S2 official_api pagination dry-run saved from source console."
      }),
    onSuccess: refreshAll
  });
  const fetchOfficialApi = useMutation({
    mutationFn: async () => {
      const dataSourceId = await ensureOfficialApiSourceId();
      await api.updateDataSourceAuth(dataSourceId, {
        auth_type: "api_key",
        secret_ref: officialApiSecretRef,
        header_name: "X-API-Key",
        reason: "AT-069 frontend official_api secret_ref saved before fetch."
      });
      await api.updateDataSourcePagination(dataSourceId, {
        strategy: "page",
        page_param: "page",
        page_size_param: "limit",
        max_pages: officialApiMaxPages,
        dry_run: true,
        reason: "AT-069 frontend pagination saved before fetch."
      });
      return api.fetchOfficialApi(dataSourceId, 2);
    },
    onSuccess: refreshAll
  });
  const runRetryBackoffProbe = useMutation({
    mutationFn: async () => {
      const created = await api.createDataSource(`S2 retry backoff source ${Date.now()}`, "official_api", {
        access_mode: "official_api",
        base_url: "synthetic://xian/official-api",
        method: "GET",
        secret_ref: officialApiSecretRef,
        schema: { records_path: "$.items", id_path: "$.id" },
        retry_policy: {
          max_attempts: 3,
          initial_delay_seconds: 5,
          multiplier: 2,
          max_delay_seconds: 30,
          jitter_seconds: 0
        }
      });
      const dataSourceId = created.data.data_source_id;
      const first = await api.fetchOfficialApi(dataSourceId, 2, "synthetic://xian/official-api/429");
      const second = await api.fetchOfficialApi(dataSourceId, 2, "synthetic://xian/official-api/429");
      const permanent = await api.fetchOfficialApi(dataSourceId, 2, "synthetic://xian/official-api/401");
      const queue = await api.opsRetryQueue();
      const deadLetters = await api.listDeadLetters({ dataSourceId, pageSize: 8 });
      return {
        dataSourceId,
        first: first.data,
        second: second.data,
        permanent: permanent.data,
        retryRows: queue.data.filter((item) => mapValue(item.payload)?.data_source_id === dataSourceId),
        deadLetters: deadLetters.data
      };
    },
    onSuccess: refreshAll
  });
  const replayDeadLetter = useMutation({
    mutationFn: async () => {
      const latestOpen401 =
        (runRetryBackoffProbe.data?.deadLetters ?? []).find((item) => item.status === "open" && item.error_code === "OFFICIAL_API_UNAUTHORIZED") ??
        (deadLetters.data?.data ?? []).find((item) => item.status === "open" && item.error_code === "OFFICIAL_API_UNAUTHORIZED");
      const deadLetterId = stringValue(latestOpen401?.dead_letter_id);
      if (!deadLetterId) throw new Error("Create an open OFFICIAL_API_UNAUTHORIZED dead letter before replay.");
      return api.replayDeadLetter(deadLetterId, {
        sourceUri: "synthetic://xian/official-api/issues",
        reason: "AT-080 frontend dead-letter replay with corrected synthetic official API URI."
      });
    },
    onSuccess: refreshAll
  });
  const createRssSource = useMutation({
    mutationFn: async () => {
      const dataSourceId = await ensureRssSourceId();
      const current = await api.listDataSources({ sourceType: "rss", pageSize: 50 });
      const source = current.data.find((item) => item.data_source_id === dataSourceId);
      if (!source) throw new Error("RSS source was not returned by backend.");
      return source;
    },
    onSuccess: refreshAll
  });
  const inspectRss = useMutation({
    mutationFn: async () => api.inspectRssFeed(await ensureRssSourceId()),
    onSuccess: refreshAll
  });
  const fetchRssItems = useMutation({
    mutationFn: async () => api.fetchRssItems(await ensureRssSourceId(), rssFeedUrl),
    onSuccess: refreshAll
  });
  const createFileUploadSource = useMutation({
    mutationFn: async () => {
      const dataSourceId = await ensureFileUploadSourceId();
      const current = await api.listDataSources({ sourceType: "file_upload", pageSize: 50 });
      const source = current.data.find((item) => item.data_source_id === dataSourceId);
      if (!source) throw new Error("File upload source was not returned by backend.");
      return source;
    },
    onSuccess: refreshAll
  });
  const receiveFileUpload = useMutation({
    mutationFn: async () => {
      if (!selectedUploadFile) throw new Error("Select a file before uploading.");
      return api.uploadFile(await ensureFileUploadSourceId(), selectedUploadFile, {
        title: selectedUploadFile.name,
        isSynthetic: false,
        sourceUri: `upload://${selectedUploadFile.name}`
      });
    },
    onSuccess: refreshAll
  });
  const uploadedFileObject = mapValue(receiveFileUpload.data?.data.file_object);
  const uploadedFileObjectId = stringValue(uploadedFileObject?.file_object_id);
  const startUploadedFileRun = useMutation({
    mutationFn: async () => {
      if (!uploadedFileObjectId) throw new Error("Upload a file before importing it.");
      const collectionJobId = await ensureFileUploadCollectionJobId();
      return api.startFileUploadRun(collectionJobId, uploadedFileObjectId, {
        title: stringValue(uploadedFileObject?.file_name) || selectedUploadFile?.name || "Uploaded file import",
        cityId: "xian",
        reason: "AT-072 frontend import uploaded file through canonical collection job file-run API.",
        payload: {
          source: "s2_source_console",
          upload_trace_id: receiveFileUpload.data?.trace_id,
          file_object_id: uploadedFileObjectId
        }
      });
    },
    onSuccess: async (result) => {
      const collectionJob = mapValue(result.data.collection_job);
      const collectionRun = mapValue(result.data.collection_run);
      const rawRecords = Array.isArray(result.data.raw_records) ? (result.data.raw_records as JsonMap[]) : [];
      const collectionJobId = stringValue(collectionJob?.collection_job_id);
      const collectionRunId = stringValue(collectionRun?.collection_run_id);
      const rawRecordId = stringValue(rawRecords[0]?.raw_record_id);
      if (collectionJobId) setSelectedJobId(collectionJobId);
      if (collectionRunId) setSelectedRunId(collectionRunId);
      if (rawRecordId) setLastLineageRawId(rawRecordId);
      await refreshAll();
      if (collectionJobId) await queryClient.invalidateQueries({ queryKey: ["s2-collection-job-detail", collectionJobId] });
      if (collectionRunId) await queryClient.invalidateQueries({ queryKey: ["s2-collection-run-steps", collectionRunId] });
    }
  });
  const createWebhookSource = useMutation({
    mutationFn: async () =>
      api.createDataSource(`S2 webhook source ${Date.now()}`, "webhook", {
        source_key: `wh-ui-${Date.now()}`
      }),
    onSuccess: async (result) => {
      const webhook = result.data.policy.webhook as { source_key?: string; endpoint_path?: string } | undefined;
      setWebhookSourceKey(webhook?.source_key ?? "");
      setWebhookEndpoint(webhook?.endpoint_path ?? "");
      setWebhookSecret(result.data.webhook_secret_once ?? "");
      await refreshAll();
    }
  });
  const sendWebhookPayload = useMutation({
    mutationFn: async () => {
      if (!webhookSourceKey || !webhookSecret) throw new Error("Create a webhook source before sending a signed payload.");
      return api.sendWebhookPayload(webhookSourceKey, webhookSecret, {
        request_id: `ui-delivery-${Date.now()}`,
        title: "Webhook Xi'an source payload",
        content: "synthetic webhook content for Xi'an public service issue.",
        city_id: "xian",
        is_synthetic: true
      });
    },
    onSuccess: refreshAll
  });
  const createManualSource = useMutation({
    mutationFn: () =>
      api.createDataSource(`S2 manual source ${Date.now()}`, "manual", {
        entry_schema: { required_fields: ["title", "content", "time", "location"], city_id: "xian" }
      }),
    onSuccess: refreshAll
  });
  const createManualRecord = useMutation({
    mutationFn: async () => {
      const location = manualLocation.trim();
      const occurredAt = manualOccurredAt.trim();
      return api.createManualRecord(await ensureManualSourceId(), {
        title: manualTitle,
        content: manualContent,
        cityId: location ? "xian" : null,
        location: location || undefined,
        occurredAt: occurredAt || undefined,
        sourceUri: manualIsSynthetic ? "synthetic://xian/manual-entry-ui" : "manual://s2-source-console",
        isSynthetic: manualIsSynthetic,
        payload: {
          location: location || undefined,
          district: location ? "beilin" : undefined,
          channel: "manual_entry",
          entry_surface: "S2SourceConsole"
        },
        reason: "AT-092 frontend manual schema validation."
      });
    },
    onSuccess: async (result) => {
      const collectionJob = mapValue(result.data.collection_job);
      const collectionRun = mapValue(result.data.collection_run);
      const rawRecord = mapValue(result.data.raw_record);
      const collectionJobId = stringValue(collectionJob?.collection_job_id);
      const collectionRunId = stringValue(collectionRun?.collection_run_id);
      const rawRecordId = stringValue(rawRecord?.raw_record_id);
      if (collectionJobId) setSelectedJobId(collectionJobId);
      if (collectionRunId) setSelectedRunId(collectionRunId);
      if (rawRecordId) setLastLineageRawId(rawRecordId);
      await refreshAll();
      if (collectionJobId) await queryClient.invalidateQueries({ queryKey: ["s2-collection-job-detail", collectionJobId] });
      if (collectionRunId) await queryClient.invalidateQueries({ queryKey: ["s2-collection-run-steps", collectionRunId] });
    }
  });
  const createDbImportSource = useMutation({
    mutationFn: () =>
      api.createDataSource(`S2 db import source ${Date.now()}`, "db_import", {
        connection_ref: "synthetic://db/xian-social-issues",
        secret_ref: "vault://s2/db-import",
        engine: "postgresql",
        is_synthetic: true
      }),
    onSuccess: refreshAll
  });
  const testDbImportConnection = useMutation({
    mutationFn: async () => api.testDataSourceConnection(await ensureDbImportSourceId(), { sample_path: "public_petition_rows", expected_status: 200 }),
    onSuccess: refreshAll
  });
  const scanDbImportTable = useMutation({
    mutationFn: async () =>
      api.scanDbImportTable(await ensureDbImportSourceId(), {
        tableName: dbImportTableName,
        cursorField: "id",
        limit: dbImportLimit,
        responseLimit: 20,
        cityId: "xian",
        reason: "AT-075 frontend scan DB import table.",
        payload: {
          source: "s2_source_console",
          entry_surface: "DB And Object Sources"
        }
      }),
    onSuccess: async (result) => {
      const collectionRun = mapValue(result.data.collection_run);
      const rawRecords = Array.isArray(result.data.raw_records) ? (result.data.raw_records as JsonMap[]) : [];
      const collectionRunId = stringValue(collectionRun?.collection_run_id);
      const rawRecordId = stringValue(rawRecords[0]?.raw_record_id);
      if (collectionRunId) setSelectedRunId(collectionRunId);
      if (rawRecordId) setLastLineageRawId(rawRecordId);
      await refreshAll();
      if (collectionRunId) await queryClient.invalidateQueries({ queryKey: ["s2-collection-run-steps", collectionRunId] });
    }
  });
  const loadDbCursorState = useMutation({
    mutationFn: async () => api.getDataSourceCursorState(await ensureDbImportSourceId()),
    onSuccess: refreshAll
  });
  const createObjectStorageSource = useMutation({
    mutationFn: () =>
      api.createDataSource(`S2 object storage source ${Date.now()}`, "object_storage", {
        bucket: "xian-evidence",
        prefix: "synthetic/public-service/",
        secret_ref: "vault://s2/object-storage",
        is_synthetic: true
      }),
    onSuccess: refreshAll
  });
  const listObjectStorage = useMutation({
    mutationFn: async () => api.listObjectStorageKeys(await ensureObjectStorageSourceId(), { max_keys: 1000 }),
    onSuccess: refreshAll
  });
  const scanObjectStoragePrefix = useMutation({
    mutationFn: async () =>
      api.scanObjectStoragePrefix(await ensureObjectStorageSourceId(), {
        prefix: objectStoragePrefix,
        limit: objectStorageScanLimit,
        responseLimit: 20,
        cityId: "xian",
        reason: "AT-076 frontend scan object storage prefix.",
        payload: {
          source: "s2_source_console",
          entry_surface: "DB And Object Sources"
        }
      }),
    onSuccess: async (result) => {
      const collectionRun = mapValue(result.data.collection_run);
      const rawRecords = Array.isArray(result.data.raw_records) ? (result.data.raw_records as JsonMap[]) : [];
      const collectionRunId = stringValue(collectionRun?.collection_run_id);
      const rawRecordId = stringValue(rawRecords[0]?.raw_record_id);
      if (collectionRunId) setSelectedRunId(collectionRunId);
      if (rawRecordId) setLastLineageRawId(rawRecordId);
      await refreshAll();
      if (collectionRunId) await queryClient.invalidateQueries({ queryKey: ["s2-collection-run-steps", collectionRunId] });
    }
  });
  const generateSynthetic = useMutation({
    mutationFn: api.generateXianSyntheticSamples,
    onSuccess: async (result) => {
      const first = result.data.raw_records[0]?.raw_record_id;
      if (first) setLastLineageRawId(first);
      await refreshAll();
    }
  });
  const createRawRepositoryBatch = useMutation({
    mutationFn: async () => {
      const dataSourceId = await ensureManualSourceId();
      const job = await api.createCollectionJob(dataSourceId, `S2 raw repository ${Date.now()}`, null, {
        source: "s2_source_console",
        repository_smoke: true
      });
      const collectionJobId = stringValue(job.data.collection_job_id);
      if (!collectionJobId) throw new Error("Raw repository collection job was not returned by backend.");
      const run = await api.startCollectionRun(collectionJobId);
      const collectionRunId = stringValue(run.data.collection_run_id);
      if (!collectionRunId) throw new Error("Raw repository collection run was not returned by backend.");
      return api.createRawRecordBatch({
        dataSourceId,
        collectionRunId,
        completeRun: true,
        syntheticCount: 3,
        responseLimit: 3,
        reason: "AT-081 frontend raw record repository smoke.",
        payload: { source: "s2_source_console", entry_surface: "Raw Records And Lineage" }
      });
    },
    onSuccess: async (result) => {
      const collectionRun = mapValue(result.data.collection_run);
      const rawRecords = Array.isArray(result.data.raw_records) ? (result.data.raw_records as JsonMap[]) : [];
      const collectionRunId = stringValue(collectionRun?.collection_run_id);
      const rawRecordId = stringValue(rawRecords[0]?.raw_record_id);
      if (collectionRunId) setSelectedRunId(collectionRunId);
      if (rawRecordId) setLastLineageRawId(rawRecordId);
      await refreshAll();
      if (collectionRunId) await queryClient.invalidateQueries({ queryKey: ["s2-collection-run-steps", collectionRunId] });
    }
  });
  const runRawHashDedupe = useMutation({
    mutationFn: async () => {
      const dataSourceId = await ensureManualSourceId();
      const externalId = `frontend-raw-hash-${Date.now()}`;
      const firstContent = "Xi'an raw hash frontend dedupe content";
      const conflictContent = "Xi'an raw hash frontend conflict content";
      const createRepositoryRun = async (label: string) => {
        const job = await api.createCollectionJob(dataSourceId, `S2 raw hash ${label} ${Date.now()}`, null, {
          source: "s2_source_console",
          raw_hash_probe: label
        });
        const collectionJobId = stringValue(job.data.collection_job_id);
        if (!collectionJobId) throw new Error("Raw hash collection job was not returned by backend.");
        const run = await api.startCollectionRun(collectionJobId);
        const collectionRunId = stringValue(run.data.collection_run_id);
        if (!collectionRunId) throw new Error("Raw hash collection run was not returned by backend.");
        return collectionRunId;
      };
      const first = await api.createRawRecordBatch({
        dataSourceId,
        collectionRunId: await createRepositoryRun("first"),
        completeRun: true,
        responseLimit: 1,
        records: [{ title: "Raw hash first", content: firstContent, externalId, isSynthetic: true }],
        reason: "AT-082 frontend raw hash first write."
      });
      const duplicate = await api.createRawRecordBatch({
        dataSourceId,
        collectionRunId: await createRepositoryRun("duplicate"),
        completeRun: true,
        responseLimit: 1,
        records: [{ title: "Raw hash duplicate", content: firstContent, externalId, isSynthetic: true }],
        reason: "AT-082 frontend raw hash duplicate write."
      });
      const conflict = await api.createRawRecordBatch({
        dataSourceId,
        collectionRunId: await createRepositoryRun("conflict"),
        completeRun: true,
        responseLimit: 1,
        records: [{ title: "Raw hash conflict", content: conflictContent, externalId, isSynthetic: true }],
        reason: "AT-082 frontend raw hash conflict write."
      });
      return { first: first.data, duplicate: duplicate.data, conflict: conflict.data };
    },
    onSuccess: async (result) => {
      const firstRecords = Array.isArray(result.first.raw_records) ? (result.first.raw_records as JsonMap[]) : [];
      const rawRecordId = stringValue(firstRecords[0]?.raw_record_id);
      if (rawRecordId) setLastLineageRawId(rawRecordId);
      await refreshAll();
    }
  });
  const importFile = useMutation({
    mutationFn: async () => api.importFile(await ensureSourceId("manual_upload", "S2 manual import source")),
    onSuccess: refreshAll
  });
  const importPublicWeb = useMutation({
    mutationFn: async () => api.importPublicWeb(await ensureSourceId("public_web", "S2 public web import source", { access_mode: "public_web" })),
    onSuccess: refreshAll
  });
  const importOfficialApi = useMutation({
    mutationFn: async () => api.importOfficialApi(await ensureSourceId("official_api", "S2 official API missing key source")),
    onSuccess: refreshAll
  });
  const importMedia = useMutation({
    mutationFn: async () => api.importMedia(await ensureImageMediaSourceId()),
    onSuccess: refreshAll
  });
  const importVideoMedia = useMutation({
    mutationFn: async () => api.importVideoMedia(await ensureVideoMediaSourceId()),
    onSuccess: refreshAll
  });
  const importLiveSegment = useMutation({
    mutationFn: async () => api.importLiveSegment(await ensureLivestreamSourceId(), String(livestreamUrlDefault)),
    onSuccess: refreshAll
  });
  const importAudioMedia = useMutation({
    mutationFn: async () => api.importAudioMedia(await ensureAudioMediaSourceId(), String(audioSourceUriDefault)),
    onSuccess: refreshAll
  });
  const runNormalization = useMutation({
    mutationFn: () => api.runNormalization(selectedRawIds()),
    onSuccess: refreshAll
  });
  const runDatetimeNormalization = useMutation({
    mutationFn: () => api.runDatetimeNormalization(selectedRawIds()),
    onSuccess: refreshAll
  });
  const runLocationNormalization = useMutation({
    mutationFn: () => api.runLocationNormalization(selectedRawIds()),
    onSuccess: refreshAll
  });
  const runSourceTrustAssignment = useMutation({
    mutationFn: () => api.runSourceTrustAssignment(selectedRawIds()),
    onSuccess: refreshAll
  });
  const runSensitiveFieldDetection = useMutation({
    mutationFn: () => api.runSensitiveFieldDetection(selectedRawIds()),
    onSuccess: refreshAll
  });
  const runSensitiveFieldRedaction = useMutation({
    mutationFn: () => api.runSensitiveFieldRedaction(selectedRawIds()),
    onSuccess: refreshAll
  });
  const runHtmlParser = useMutation({
    mutationFn: () => api.runHtmlMainContentParser(selectedRawIds()),
    onSuccess: refreshAll
  });
  const runJsonParser = useMutation({
    mutationFn: () => api.runJsonByMappingParser(selectedRawIds()),
    onSuccess: refreshAll
  });
  const runRssParser = useMutation({
    mutationFn: () => api.runRssItemParser(selectedRssRawIds()),
    onSuccess: refreshAll
  });
  const runCsvParser = useMutation({
    mutationFn: () => api.runCsvFileParser(selectedCsvRawIds()),
    onSuccess: refreshAll
  });
  const runXlsxParser = useMutation({
    mutationFn: () => api.runXlsxFileParser(selectedXlsxRawIds()),
    onSuccess: refreshAll
  });
  const runPdfParser = useMutation({
    mutationFn: () => api.runPdfTextParser(selectedPdfRawIds()),
    onSuccess: refreshAll
  });
  const runDocxParser = useMutation({
    mutationFn: () => api.runDocxTextParser(selectedDocxRawIds()),
    onSuccess: refreshAll
  });
  const runDeduplication = useMutation({
    mutationFn: () => api.runDeduplication(selectedRawIds()),
    onSuccess: refreshAll
  });
  const runSemanticDeduplication = useMutation({
    mutationFn: () => api.runSemanticDeduplication(selectedRawIds()),
    onSuccess: refreshAll
  });
  const confirmDedupeCandidate = useMutation({
    mutationFn: () => {
      const target = semanticDecisionTarget();
      if (!target) throw new Error("Run Semantic Dedupe before confirming a candidate.");
      return api.applyDedupeDecision(target.rawRecordId, {
        decision: "confirm_duplicate",
        dedup_group_id: target.groupId,
        reason: "AT-101 frontend confirmed semantic dedupe candidate."
      });
    },
    onSuccess: refreshAll
  });
  const splitDedupeCandidate = useMutation({
    mutationFn: () => {
      const target = semanticDecisionTarget();
      if (!target) throw new Error("Run Semantic Dedupe before splitting a candidate.");
      return api.applyDedupeDecision(target.rawRecordId, {
        decision: "split_candidate",
        dedup_group_id: target.groupId,
        reason: "AT-101 frontend split semantic dedupe candidate."
      });
    },
    onSuccess: refreshAll
  });
  const updateCleanRecordStatus = useMutation({
    mutationFn: ({ status, reason }: { status: "valid" | "invalid" | "review_required"; reason: string }) => {
      if (!selectedCleanRecordId) throw new Error("Select a clean record before changing status.");
      return api.updateCleanRecordStatus(selectedCleanRecordId, status, reason);
    },
    onSuccess: refreshAll
  });
  const runQuality = useMutation({
    mutationFn: () => {
      const rawRecordIds = selectedQualityRawIds();
      if (!rawRecordIds.length) throw new Error("No clean or raw records are available for quality scoring.");
      return api.runDataQuality(rawRecordIds);
    },
    onSuccess: refreshAll
  });
  const exportSelectedRawRecord = useMutation({
    mutationFn: () => api.exportRawRecordRedacted(lastLineageRawId),
    onSuccess: refreshAll
  });

  const rawRows = rawRecords.data?.data ?? [];
  const cleanRows = cleanRecords.data?.data ?? [];
  const qualityIssueRows = qualityIssues.data?.data ?? [];
  const deadLetterRows = deadLetters.data?.data ?? [];
  const sourceRows = sources.data?.data ?? [];
  const jobRows = collectionJobs.data?.data ?? [];
  const runRows = collectionRuns.data?.data ?? [];
  const jobDetailData = collectionJobDetail.data?.data;
  const runStepsData = collectionRunSteps.data?.data;
  const importWebRun = importPublicWeb.data?.data.import_run as JsonMap | undefined;
  const importWebActivity = importWebRun?.payload && typeof importWebRun.payload === "object" ? ((importWebRun.payload as JsonMap).fetch_activity as JsonMap | undefined) : undefined;
  const htmlParserData = runHtmlParser.data?.data as JsonMap | undefined;
  const htmlParserSummary = htmlParserData?.parser as JsonMap | undefined;
  const htmlParserOutputs = Array.isArray(htmlParserData?.outputs) ? (htmlParserData.outputs as JsonMap[]) : [];
  const jsonParserData = runJsonParser.data?.data as JsonMap | undefined;
  const jsonParserSummary = jsonParserData?.parser as JsonMap | undefined;
  const jsonParserOutputs = Array.isArray(jsonParserData?.outputs) ? (jsonParserData.outputs as JsonMap[]) : [];
  const jsonMapping = mapValue(jsonParserSummary?.mapping) ?? { title: "$.title", body: "$.summary", published_at: "$.published_at" };
  const rssParserData = runRssParser.data?.data as JsonMap | undefined;
  const rssParserSummary = rssParserData?.parser as JsonMap | undefined;
  const rssParserOutputs = Array.isArray(rssParserData?.outputs) ? (rssParserData.outputs as JsonMap[]) : [];
  const csvParserData = runCsvParser.data?.data as JsonMap | undefined;
  const csvParserSummary = csvParserData?.parser as JsonMap | undefined;
  const csvParserOutputs = Array.isArray(csvParserData?.outputs) ? (csvParserData.outputs as JsonMap[]) : [];
  const csvMapping = mapValue(csvParserSummary?.mapping) ?? { title: "title", body: "content", published_at: "published_at" };
  const xlsxParserData = runXlsxParser.data?.data as JsonMap | undefined;
  const xlsxParserSummary = xlsxParserData?.parser as JsonMap | undefined;
  const xlsxParserOutputs = Array.isArray(xlsxParserData?.outputs) ? (xlsxParserData.outputs as JsonMap[]) : [];
  const xlsxMapping = mapValue(xlsxParserSummary?.mapping) ?? { title: "title", body: "content", published_at: "published_at" };
  const pdfParserData = runPdfParser.data?.data as JsonMap | undefined;
  const pdfParserSummary = pdfParserData?.parser as JsonMap | undefined;
  const pdfParserOutputs = Array.isArray(pdfParserData?.outputs) ? (pdfParserData.outputs as JsonMap[]) : [];
  const docxParserData = runDocxParser.data?.data as JsonMap | undefined;
  const docxParserSummary = docxParserData?.parser as JsonMap | undefined;
  const docxParserOutputs = Array.isArray(docxParserData?.outputs) ? (docxParserData.outputs as JsonMap[]) : [];
  const officialApiRun = fetchOfficialApi.data?.data.import_run as JsonMap | undefined;
  const officialApiActivity = officialApiRun?.payload && typeof officialApiRun.payload === "object" ? ((officialApiRun.payload as JsonMap).official_api_activity as JsonMap | undefined) : undefined;
  const retryBackoffRows = [...(runRetryBackoffProbe.data?.retryRows ?? [])].sort((left, right) => Number(left.attempts ?? 0) - Number(right.attempts ?? 0));
  const retryBackoffDelays = retryBackoffRows
    .map((row) => mapValue(mapValue(row.payload)?.retry_policy)?.next_delay_seconds)
    .filter((value) => typeof value === "number")
    .join("/");
  const retryBackoffPermanent = mapValue(mapValue(runRetryBackoffProbe.data?.permanent.import_run)?.payload)?.retry_policy;
  const retryBackoffDeadLetters = runRetryBackoffProbe.data?.deadLetters ?? [];
  const replayDeadLetterData = mapValue(replayDeadLetter.data?.data.replay);
  const replayDeadLetterResult = mapValue(replayDeadLetter.data?.data.replay_result);
  const replayDeadLetterImport = mapValue(replayDeadLetterResult?.import_run);
  const channelReplayRun = mapValue(replayChannelCheckpoint.data?.replay);
  const channelReplayPayload = mapValue(channelReplayRun?.payload);
  const channelReplayCheckpoint = mapValue(channelReplayPayload?.channel_checkpoint);
  const channelReplayGuard = mapValue(channelReplayPayload?.raw_replay_guard);
  const normalizationData = runNormalization.data?.data as JsonMap | undefined;
  const normalizationSummary = mapValue(normalizationData?.cleaner);
  const normalizationOutputs = Array.isArray(normalizationData?.outputs) ? (normalizationData.outputs as JsonMap[]) : [];
  const datetimeNormalizationData = runDatetimeNormalization.data?.data as JsonMap | undefined;
  const datetimeNormalizationSummary = mapValue(datetimeNormalizationData?.cleaner);
  const datetimeNormalizationOutputs = Array.isArray(datetimeNormalizationData?.outputs) ? (datetimeNormalizationData.outputs as JsonMap[]) : [];
  const locationNormalizationData = runLocationNormalization.data?.data as JsonMap | undefined;
  const locationNormalizationSummary = mapValue(locationNormalizationData?.cleaner);
  const locationNormalizationOutputs = Array.isArray(locationNormalizationData?.outputs) ? (locationNormalizationData.outputs as JsonMap[]) : [];
  const sourceTrustData = runSourceTrustAssignment.data?.data as JsonMap | undefined;
  const sourceTrustSummary = mapValue(sourceTrustData?.cleaner);
  const sourceTrustOutputs = Array.isArray(sourceTrustData?.outputs) ? (sourceTrustData.outputs as JsonMap[]) : [];
  const sensitiveDetectionData = runSensitiveFieldDetection.data?.data as JsonMap | undefined;
  const sensitiveDetectionSummary = mapValue(sensitiveDetectionData?.detector);
  const sensitiveDetectionTypeCounts = mapValue(sensitiveDetectionSummary?.type_counts);
  const sensitiveDetectionTypes = sensitiveDetectionTypeCounts
    ? Object.entries(sensitiveDetectionTypeCounts)
        .filter(([, count]) => Number(count) > 0)
        .map(([fieldType]) => fieldType)
        .sort()
    : [];
  const sensitiveRedactionData = runSensitiveFieldRedaction.data?.data as JsonMap | undefined;
  const sensitiveRedactionSummary = mapValue(sensitiveRedactionData?.cleaner);
  const sensitiveRedactionTypeCounts = mapValue(sensitiveRedactionSummary?.type_counts);
  const sensitiveRedactionTypes = sensitiveRedactionTypeCounts
    ? Object.entries(sensitiveRedactionTypeCounts)
        .filter(([, count]) => Number(count) > 0)
        .map(([fieldType]) => fieldType)
        .sort()
    : [];
  const deduplicationData = runDeduplication.data?.data as JsonMap | undefined;
  const deduplicationSummary = mapValue(deduplicationData?.deduper);
  const semanticDeduplicationData = runSemanticDeduplication.data?.data as JsonMap | undefined;
  const semanticDeduplicationSummary = mapValue(semanticDeduplicationData?.semantic_deduper);
  const semanticDecisionData = (confirmDedupeCandidate.data?.data ?? splitDedupeCandidate.data?.data) as JsonMap | undefined;
  const semanticDecision = mapValue(semanticDecisionData?.decision);
  const qualityData = runQuality.data?.data as JsonMap | undefined;
  const qualitySummary = mapValue(qualityData?.quality_scorer);
  const rssFetchRun = fetchRssItems.data?.data.import_run as JsonMap | undefined;
  const rssFetchActivity = rssFetchRun?.payload && typeof rssFetchRun.payload === "object" ? ((rssFetchRun.payload as JsonMap).rss_activity as JsonMap | undefined) : undefined;
  const fileImportRun = startUploadedFileRun.data?.data.import_run as JsonMap | undefined;
  const fileCollectionRun = startUploadedFileRun.data?.data.collection_run as JsonMap | undefined;
  const fileRawRecords = Array.isArray(startUploadedFileRun.data?.data.raw_records) ? (startUploadedFileRun.data.data.raw_records as JsonMap[]) : [];
  const manualRecordRaw = mapValue(createManualRecord.data?.data.raw_record);
  const manualRecordRun = mapValue(createManualRecord.data?.data.collection_run);
  const manualRecordValidation = mapValue(createManualRecord.data?.data.validation);
  const manualRecordCleanDraft = mapValue(createManualRecord.data?.data.clean_draft);
  const manualRecordCleanDraftPayload = mapValue(manualRecordCleanDraft?.payload);
  const rawRepositoryData = mapValue(createRawRepositoryBatch.data?.data.repository);
  const rawRepositoryRun = mapValue(createRawRepositoryBatch.data?.data.collection_run);
  const rawHashDuplicateRepo = mapValue(runRawHashDedupe.data?.duplicate.repository);
  const rawHashConflictRepo = mapValue(runRawHashDedupe.data?.conflict.repository);
  const dbScanRun = mapValue(scanDbImportTable.data?.data.import_run);
  const dbScanActivity = mapValue(dbScanRun?.payload && typeof dbScanRun.payload === "object" ? (dbScanRun.payload as JsonMap).db_import_activity : undefined);
  const dbCursor = loadDbCursorState.data?.data.cursors[0];
  const dbCursorGuard = loadDbCursorState.data?.data.failure_guard;
  const objectScanRun = mapValue(scanObjectStoragePrefix.data?.data.import_run);
  const objectScanActivity = mapValue(objectScanRun?.payload && typeof objectScanRun.payload === "object" ? (objectScanRun.payload as JsonMap).object_storage_activity : undefined);
  const rateLimitView = loadRateLimitStats.data?.data ?? rateLimitStats.data?.data ?? runRateLimitTwice.data?.stats;
  const webPageQualityView = webPageQualityMetrics.data?.data;
  const rssQualityView = rssQualityMetrics.data?.data;
  const channelMaintenanceView = channelMaintenance.data?.data;
  const channelMaintenanceRows = Array.isArray(channelMaintenanceView?.channels) ? channelMaintenanceView.channels : [];
  const healthRows = health.data?.data.sources ?? [];
  const adapterRows = adapterCapabilities.data?.data ?? [];
  const channelRows = collectionChannels.data?.data ?? [];
  const channelErrorMap = channelErrorCodes.data?.data;
  const sourceById = new Map<string, DataSourceRecord>(sourceRows.map((source) => [source.data_source_id, source]));
  const errorMappingsByChannelAndCode = new Map<string, ChannelErrorMapping>();
  const errorMappingsByCode = new Map<string, ChannelErrorMapping[]>();
  const errorFallbackByChannel = new Map<string, { classification: string; severity: "warning"; retryable: false; warning_code: string }>();
  for (const channel of channelErrorMap?.channels ?? []) {
    errorFallbackByChannel.set(channel.channel, channel.fallback);
    for (const mapping of channel.mappings ?? []) {
      errorMappingsByChannelAndCode.set(`${mapping.channel}:${mapping.error_code}`, mapping);
      const existing = errorMappingsByCode.get(mapping.error_code) ?? [];
      existing.push(mapping);
      errorMappingsByCode.set(mapping.error_code, existing);
    }
  }
  const adapterContractData = adapterContract.data?.data;
  const webPageSchemaData = webPageChannelSchema.data?.data;
  const officialApiSchemaData = officialApiChannelSchema.data?.data;
  const documentFileSchemaData = documentFileChannelSchema.data?.data;
  const imageFileSchemaData = imageFileChannelSchema.data?.data;
  const videoFileSchemaData = videoFileChannelSchema.data?.data;
  const livestreamSchemaData = livestreamChannelSchema.data?.data;
  const audioFileSchemaData = audioFileChannelSchema.data?.data;
  const documentFileProperties = mapValue(mapValue(documentFileSchemaData?.json_schema)?.properties);
  const documentAllowedTypeItems = mapValue(mapValue(documentFileProperties?.allowed_file_types)?.items);
  const documentAllowedTypes = Array.isArray(documentAllowedTypeItems?.enum) ? documentAllowedTypeItems.enum.filter((item): item is string => typeof item === "string") : [];
  const documentSchemaReady = documentFileSchemaData?.status === "ready" && documentAllowedTypes.length > 0;
  const documentFileAccept = documentAllowedTypes.map((item) => `.${item}`).join(",");
  const imageFileProperties = mapValue(mapValue(imageFileSchemaData?.json_schema)?.properties);
  const imageFormatItems = mapValue(mapValue(imageFileProperties?.allowed_formats)?.items);
  const imageUiFields = Array.isArray(mapValue(imageFileSchemaData?.ui_schema)?.fields) ? (mapValue(imageFileSchemaData?.ui_schema)?.fields as unknown[]).map(mapValue).filter((item): item is JsonMap => Boolean(item)) : [];
  const imageFieldDefault = (name: string): unknown => imageUiFields.find((field) => field.name === name)?.default;
  const imageAllowedFormats = stringArrayValue(imageFieldDefault("allowed_formats") ?? mapValue(imageFileProperties?.allowed_formats)?.default ?? imageFormatItems?.enum);
  const imageOcrPolicy = mapValue(imageFieldDefault("ocr_policy"));
  const imageVlmPolicy = mapValue(imageFieldDefault("vlm_policy"));
  const imageRedactionPolicy = mapValue(imageFieldDefault("redaction_policy"));
  const imageMaxSizeDefault = imageFieldDefault("max_file_size_mb") ?? mapValue(imageFileProperties?.max_file_size_mb)?.default;
  const imageSchemaReady = imageFileSchemaData?.status === "ready" && imageAllowedFormats.length > 0 && Boolean(imageOcrPolicy) && Boolean(imageVlmPolicy) && Boolean(imageRedactionPolicy) && typeof imageMaxSizeDefault === "number";
  const videoFileProperties = mapValue(mapValue(videoFileSchemaData?.json_schema)?.properties);
  const videoFormatItems = mapValue(mapValue(videoFileProperties?.allowed_formats)?.items);
  const videoUiFields = Array.isArray(mapValue(videoFileSchemaData?.ui_schema)?.fields) ? (mapValue(videoFileSchemaData?.ui_schema)?.fields as unknown[]).map(mapValue).filter((item): item is JsonMap => Boolean(item)) : [];
  const videoFieldDefault = (name: string): unknown => videoUiFields.find((field) => field.name === name)?.default;
  const videoAllowedFormats = stringArrayValue(videoFieldDefault("allowed_formats") ?? mapValue(videoFileProperties?.allowed_formats)?.default ?? videoFormatItems?.enum);
  const videoKeyframePolicy = mapValue(videoFieldDefault("keyframe_policy"));
  const videoAsrPolicy = mapValue(videoFieldDefault("asr_policy"));
  const videoOcrPolicy = mapValue(videoFieldDefault("ocr_policy"));
  const videoVlmPolicy = mapValue(videoFieldDefault("vlm_policy"));
  const videoLargePolicy = mapValue(videoFieldDefault("large_video_policy"));
  const videoRedactionPolicy = mapValue(videoFieldDefault("redaction_policy"));
  const videoMaxSizeDefault = videoFieldDefault("max_file_size_mb") ?? mapValue(videoFileProperties?.max_file_size_mb)?.default;
  const videoSchemaReady = videoFileSchemaData?.status === "ready" && videoAllowedFormats.length > 0 && Boolean(videoKeyframePolicy) && Boolean(videoAsrPolicy) && Boolean(videoOcrPolicy) && Boolean(videoVlmPolicy) && Boolean(videoLargePolicy) && typeof videoMaxSizeDefault === "number";
  const livestreamProperties = mapValue(mapValue(livestreamSchemaData?.json_schema)?.properties);
  const livestreamUiFields = Array.isArray(mapValue(livestreamSchemaData?.ui_schema)?.fields) ? (mapValue(livestreamSchemaData?.ui_schema)?.fields as unknown[]).map(mapValue).filter((item): item is JsonMap => Boolean(item)) : [];
  const livestreamFieldDefault = (name: string): unknown => livestreamUiFields.find((field) => field.name === name)?.default;
  const livestreamUrlDefault = livestreamFieldDefault("stream_url") ?? mapValue(livestreamProperties?.stream_url)?.default;
  const livestreamProtocolDefault = livestreamFieldDefault("stream_protocol") ?? mapValue(livestreamProperties?.stream_protocol)?.default;
  const livestreamSegmentPolicy = mapValue(livestreamFieldDefault("segment_policy"));
  const livestreamBufferPolicy = mapValue(livestreamFieldDefault("buffer_policy"));
  const livestreamRetentionPolicy = mapValue(livestreamFieldDefault("retention_policy"));
  const livestreamRedactionPolicy = mapValue(livestreamFieldDefault("redaction_policy"));
  const livestreamSchemaReady = livestreamSchemaData?.status === "ready" && typeof livestreamUrlDefault === "string" && livestreamUrlDefault.length > 0 && Boolean(livestreamProtocolDefault) && Boolean(livestreamSegmentPolicy) && Boolean(livestreamBufferPolicy) && Boolean(livestreamRetentionPolicy);
  const audioFileProperties = mapValue(mapValue(audioFileSchemaData?.json_schema)?.properties);
  const audioFormatItems = mapValue(mapValue(audioFileProperties?.allowed_formats)?.items);
  const audioUiFields = Array.isArray(mapValue(audioFileSchemaData?.ui_schema)?.fields) ? (mapValue(audioFileSchemaData?.ui_schema)?.fields as unknown[]).map(mapValue).filter((item): item is JsonMap => Boolean(item)) : [];
  const audioFieldDefault = (name: string): unknown => audioUiFields.find((field) => field.name === name)?.default;
  const audioAllowedFormats = stringArrayValue(audioFieldDefault("allowed_formats") ?? mapValue(audioFileProperties?.allowed_formats)?.default ?? audioFormatItems?.enum);
  const audioAsrPolicy = mapValue(audioFieldDefault("asr_policy"));
  const audioSegmentationPolicy = mapValue(audioFieldDefault("segmentation_policy"));
  const audioLanguagePolicy = mapValue(audioFieldDefault("language_policy"));
  const audioRedactionPolicy = mapValue(audioFieldDefault("redaction_policy"));
  const audioMaxSizeDefault = audioFieldDefault("max_file_size_mb") ?? mapValue(audioFileProperties?.max_file_size_mb)?.default;
  const audioSourceUriDefault = audioFieldDefault("source_uri") ?? mapValue(audioFileProperties?.source_uri)?.default;
  const audioSchemaReady = audioFileSchemaData?.status === "ready" && audioAllowedFormats.length > 0 && Boolean(audioAsrPolicy) && Boolean(audioSegmentationPolicy) && Boolean(audioLanguagePolicy) && typeof audioMaxSizeDefault === "number" && typeof audioSourceUriDefault === "string" && audioSourceUriDefault.length > 0;
  const channelWarningCount = channelRows.filter((item) => item.warnings.length > 0).length;
  const channelForSource = (source?: DataSourceRecord): string => {
    if (!source) return "";
    if (source.source_type === "public_web") return "web_page";
    if (source.source_type === "official_api") return "official_api";
    if (source.source_type === "rss") return "rss";
    if (source.source_type === "file_upload" || source.source_type === "manual_upload") return "document_file";
    if (source.source_type === "live_segment") return "livestream";
    if (source.source_type === "db_import") return "database";
    if (source.source_type === "object_storage") return "object_storage";
    if (source.source_type === "webhook") return "webhook";
    if (source.source_type === "media") {
      const mediaKind = stringValue(source.policy?.media_kind);
      if (["image_file", "video_file", "audio_file"].includes(mediaKind)) return mediaKind;
      const mediaTypes = stringArrayValue(source.policy?.media_types);
      if (mediaTypes.includes("video")) return "video_file";
      if (mediaTypes.includes("audio")) return "audio_file";
      return "image_file";
    }
    return source.source_type;
  };
  const resolveChannelError = (dataSourceId?: string | null, errorCode?: string | null): ChannelErrorMapping | undefined => {
    if (!errorCode) return undefined;
    const channel = channelForSource(dataSourceId ? sourceById.get(dataSourceId) : undefined);
    const exact = channel ? errorMappingsByChannelAndCode.get(`${channel}:${errorCode}`) : undefined;
    if (exact) return exact;
    const crossChannel = errorMappingsByCode.get(errorCode)?.[0];
    if (crossChannel) return crossChannel;
    const fallback = errorFallbackByChannel.get(channel || "web_page");
    if (!fallback) return undefined;
    return {
      channel: channel || "unknown",
      error_code: errorCode,
      known: false,
      label: "Unmapped channel error",
      classification: fallback.classification,
      severity: fallback.severity,
      retryable: fallback.retryable,
      remediation: "Register this code in the backend map_channel_error_codes service.",
      run_detail_hint: `Unmapped ${channel || "unknown"} error ${errorCode}; inspect persisted run, import, and source health payloads.`,
      source: "map_channel_error_codes"
    };
  };
  const selectedRunRecord = runRows.find((run) => run.collection_run_id === selectedRunId);
  const selectedRunError = resolveChannelError(selectedRunRecord?.data_source_id, selectedRunRecord?.error_code);
  const firstDeadLetterError = resolveChannelError(stringValue(deadLetterRows[0]?.data_source_id), stringValue(deadLetterRows[0]?.error_code));
  const firstImportRun = (importRuns.data?.data ?? []).find((run) => Boolean(run.error_code));
  const firstImportRunError = resolveChannelError(stringValue(firstImportRun?.data_source_id), stringValue(firstImportRun?.error_code));
  const jobPagination = collectionJobs.data?.meta?.pagination as { page?: number; page_size?: number; total?: number } | undefined;
  const runPagination = collectionRuns.data?.meta?.pagination as { page?: number; page_size?: number; total?: number } | undefined;
  const cleanPagination = cleanRecords.data?.meta?.pagination as { page?: number; page_size?: number; total?: number } | undefined;
  const cleanPageState = String(cleanRecords.data?.meta?.page_state ?? (cleanRecords.isFetching ? "loading" : "unknown"));
  const qualityIssuePagination = qualityIssues.data?.meta?.pagination as { page?: number; page_size?: number; total?: number } | undefined;
  const qualityIssueState = String(qualityIssues.data?.meta?.page_state ?? (qualityIssues.isFetching ? "loading" : "unknown"));
  const qualityIssueSummary = mapValue(qualityIssues.data?.meta?.summary);
  const cleanDetailData = cleanRecordDetail.data?.data;
  const cleanDetailLatest = mapValue(cleanDetailData?.clean.latest_normalization);
  const cleanDetailSignals = Array.isArray(cleanDetailData?.extractions.signals) ? (cleanDetailData.extractions.signals as JsonMap[]) : [];
  const cleanDetailIssues = Array.isArray(cleanDetailData?.quality.issues) ? (cleanDetailData.quality.issues as JsonMap[]) : [];
  const cleanDetailEdges = Array.isArray(cleanDetailData?.lineage.edges) ? (cleanDetailData.lineage.edges as JsonMap[]) : [];
  const runMetricData = collectionRunMetrics.data?.data;
  const syntheticCount = useMemo(() => rawRows.filter((row) => row.is_synthetic).length, [rawRows]);
  const loading = types.isLoading || collectionChannels.isLoading || adapterContract.isLoading || channelErrorCodes.isLoading || webPageQualityMetrics.isLoading || rssQualityMetrics.isLoading || channelMaintenance.isLoading || webPageChannelSchema.isLoading || officialApiChannelSchema.isLoading || documentFileChannelSchema.isLoading || imageFileChannelSchema.isLoading || videoFileChannelSchema.isLoading || livestreamChannelSchema.isLoading || audioFileChannelSchema.isLoading || adapterCapabilities.isLoading || sources.isLoading || collectionJobs.isLoading || collectionJobDetail.isLoading || collectionRuns.isLoading || collectionRunSteps.isLoading || collectionRunMetrics.isLoading || health.isLoading || healthDetail.isLoading || rateLimitStats.isLoading || rawRecords.isLoading || cleanRecords.isLoading || qualityIssues.isLoading || cleanRecordDetail.isLoading || rawDetail.isLoading || importRuns.isLoading || deadLetters.isLoading;
  const denied = permissions.isSuccess && !canRead;
  const degraded = health.data?.data.page_state === "degraded" || channelMaintenanceView?.page_state === "degraded" || sourceRows.some((row) => row.status === "blocked");
  const firstError = [permissions, types, collectionChannels, adapterContract, channelErrorCodes, webPageQualityMetrics, rssQualityMetrics, channelMaintenance, webPageChannelSchema, officialApiChannelSchema, documentFileChannelSchema, imageFileChannelSchema, videoFileChannelSchema, livestreamChannelSchema, audioFileChannelSchema, adapterCapabilities, sources, collectionJobs, collectionJobDetail, collectionRuns, collectionRunSteps, collectionRunMetrics, health, healthDetail, rateLimitStats, rawRecords, cleanRecords, qualityIssues, cleanRecordDetail, rawDetail, importRuns, deadLetters, normalizationRuns, deduplicationRuns, qualityRuns, lineage].find((query) => query.isError)?.error as Error | undefined;

  async function ensureSourceId(sourceTypeValue: string, name: string, policy = {}) {
    const current = await api.listDataSources({ sourceType: sourceTypeValue, pageSize: 100 });
    const existing = current.data.find((item) => item.source_type === sourceTypeValue && item.name === name);
    if (existing) return existing.data_source_id;
    const created = await api.createDataSource(name, sourceTypeValue, policy);
    return created.data.data_source_id;
  }

  function rssSourceName(feedUrl: string) {
    let hash = 0;
    for (const char of feedUrl) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
    return `S2 RSS synthetic source ${hash.toString(36)}`;
  }

  async function ensureOfficialApiSourceId() {
    return ensureSourceId("official_api", "S2 official API synthetic source", {
      access_mode: "official_api",
      base_url: officialApiBaseUrl,
      method: "GET",
      schema: { records_path: "$.items", id_path: "$.id" }
    });
  }

  async function ensureRssSourceId() {
    return ensureSourceId("rss", rssSourceName(rssFeedUrl), {
      access_mode: "public_web",
      feed_url: rssFeedUrl
    });
  }

  async function ensureFileUploadSourceId() {
    if (!documentSchemaReady) throw new Error("Document file schema is required before creating a file_upload source.");
    return ensureSourceId("file_upload", "S2 file upload source", {
      allowed_file_types: documentAllowedTypes,
      schema: { title_field: "title", content_field: "content", occurred_at_field: "published_at", location_field: "location", city_id: "xian" },
      max_file_size_mb: 50
    });
  }

  async function ensureImageMediaSourceId() {
    if (!imageSchemaReady) throw new Error("Image file schema is required before importing image media.");
    return ensureSourceId("media", "S2 image media import source", {
      allowed_formats: imageAllowedFormats,
      ocr_policy: imageOcrPolicy,
      vlm_policy: imageVlmPolicy,
      redaction_policy: imageRedactionPolicy,
      max_file_size_mb: imageMaxSizeDefault
    });
  }

  async function ensureVideoMediaSourceId() {
    if (!videoSchemaReady) throw new Error("Video file schema is required before importing video media.");
    return ensureSourceId("media", "S2 video media import source", {
      media_kind: "video_file",
      allowed_formats: videoAllowedFormats,
      keyframe_policy: videoKeyframePolicy,
      asr_policy: videoAsrPolicy,
      ocr_policy: videoOcrPolicy,
      vlm_policy: videoVlmPolicy,
      large_video_policy: videoLargePolicy,
      redaction_policy: videoRedactionPolicy,
      max_file_size_mb: videoMaxSizeDefault
    });
  }

  async function ensureLivestreamSourceId() {
    if (!livestreamSchemaReady) throw new Error("Livestream schema is required before importing live segments.");
    return ensureSourceId("live_segment", "S2 livestream segment source", {
      stream_url: livestreamUrlDefault,
      stream_protocol: livestreamProtocolDefault,
      segment_policy: livestreamSegmentPolicy,
      buffer_policy: livestreamBufferPolicy,
      retention_policy: livestreamRetentionPolicy,
      redaction_policy: livestreamRedactionPolicy,
      is_synthetic: true
    });
  }

  async function ensureAudioMediaSourceId() {
    if (!audioSchemaReady) throw new Error("Audio file schema is required before importing audio media.");
    return ensureSourceId("media", "S2 audio media import source", {
      media_kind: "audio_file",
      allowed_formats: audioAllowedFormats,
      asr_policy: audioAsrPolicy,
      segmentation_policy: audioSegmentationPolicy,
      language_policy: audioLanguagePolicy,
      redaction_policy: audioRedactionPolicy,
      max_file_size_mb: audioMaxSizeDefault
    });
  }

  async function ensureManualSourceId() {
    return ensureSourceId("manual", "S2 manual schema validator source", {
      entry_schema: { required_fields: ["title", "content", "time", "location"], city_id: "xian" }
    });
  }

  async function ensureFileUploadCollectionJobId() {
    const dataSourceId = await ensureFileUploadSourceId();
    const current = await api.listCollectionJobs({ dataSourceId, pageSize: 100 });
    const existing = current.data.find((item) => item.data_source_id === dataSourceId && item.name === "S2 file upload import job" && item.status === "active");
    if (existing) return existing.collection_job_id;
    const created = await api.createCollectionJob(dataSourceId, "S2 file upload import job", null, {
      source_type: "file_upload",
      city_id: "xian",
      import_mode: "uploaded_file",
      source: "s2_source_console"
    });
    const createdId = stringValue(created.data.collection_job_id);
    if (createdId) return createdId;
    const refreshed = await api.listCollectionJobs({ dataSourceId, pageSize: 100 });
    const createdMatch = refreshed.data.find((item) => item.data_source_id === dataSourceId && item.name === "S2 file upload import job");
    if (createdMatch) return createdMatch.collection_job_id;
    throw new Error("File upload collection job was not returned by backend.");
  }

  async function ensureDbImportSourceId() {
    return ensureSourceId("db_import", "S2 DB import synthetic source", {
      connection_ref: "synthetic://db/xian-social-issues",
      secret_ref: "vault://s2/db-import",
      engine: "postgresql",
      is_synthetic: true
    });
  }

  async function ensureObjectStorageSourceId() {
    return ensureSourceId("object_storage", "S2 object storage synthetic source", {
      bucket: "xian-evidence",
      prefix: "synthetic/public-service/",
      secret_ref: "vault://s2/object-storage",
      is_synthetic: true
    });
  }

  async function createRateLimitJobPair() {
    const suffix = Date.now();
    const source = await api.createDataSource(`S2 rate limit synthetic source ${suffix}`, "synthetic", {
      access_mode: "test_fixture",
      is_synthetic: true,
      channel_rate_limits: {
        web_page: {
          max_runs: 1,
          window_seconds: 60,
          delay_seconds: 60,
          scope: "channel",
          mode: "sliding_window"
        },
        rss: {
          max_runs: 1,
          window_seconds: 60,
          delay_seconds: 60,
          scope: "channel",
          mode: "sliding_window"
        }
      }
    });
    const dataSourceId = source.data.data_source_id;
    const first = await api.createCollectionJob(dataSourceId, `S2 rate limit first ${suffix}`, null, {
      source: "s2_source_console",
      rate_limit_probe: true,
      collection_channel: "web_page",
      sequence: 1
    });
    const second = await api.createCollectionJob(dataSourceId, `S2 rate limit second ${suffix}`, null, {
      source: "s2_source_console",
      rate_limit_probe: true,
      collection_channel: "web_page",
      sequence: 2
    });
    const rss = await api.createCollectionJob(dataSourceId, `S2 rate limit rss ${suffix}`, null, {
      source: "s2_source_console",
      rate_limit_probe: true,
      collection_channel: "rss",
      sequence: 3
    });
    const webJobIds = [stringValue(first.data.collection_job_id), stringValue(second.data.collection_job_id)].filter(Boolean);
    const rssJobId = stringValue(rss.data.collection_job_id);
    const jobIds = [...webJobIds, rssJobId].filter(Boolean);
    if (webJobIds.length !== 2 || !rssJobId || jobIds.length !== 3) throw new Error("Rate limit collection jobs were not returned by backend.");
    setRateLimitSourceId(dataSourceId);
    setRateLimitJobIds(jobIds);
    return { dataSourceId, jobIds, webJobIds, rssJobId };
  }

  function selectedRawIds() {
    return rawRows.slice(0, 12).map((record) => record.raw_record_id);
  }

  function selectedQualityRawIds() {
    if (selectedCleanRecordId) return [selectedCleanRecordId];
    const cleanPageIds = cleanRows.slice(0, 12).map((record) => record.raw_record_id).filter(Boolean);
    return cleanPageIds.length ? cleanPageIds : selectedRawIds();
  }

  function semanticDecisionTarget() {
    const groups = Array.isArray(semanticDeduplicationData?.groups) ? (semanticDeduplicationData.groups as JsonMap[]) : [];
    const group = groups.find((item) => Boolean(item.dedup_group_id) && Array.isArray(item.duplicate_raw_record_ids) && item.duplicate_raw_record_ids.length > 0);
    if (!group) return null;
    const duplicateIds = group.duplicate_raw_record_ids as unknown[];
    const rawRecordId = stringValue(duplicateIds[0]);
    const groupId = stringValue(group.dedup_group_id);
    return rawRecordId && groupId ? { rawRecordId, groupId } : null;
  }

  function selectedRssRawIds() {
    const fetchedRawRecords = Array.isArray(fetchRssItems.data?.data.raw_records) ? (fetchRssItems.data.data.raw_records as JsonMap[]) : [];
    const fetchedRawIds = fetchedRawRecords.map((record) => stringValue(record.raw_record_id)).filter(Boolean);
    if (fetchedRawIds.length > 0) return fetchedRawIds.slice(0, 50);
    return rawRows.filter((record) => record.source_type === "rss").slice(0, 50).map((record) => record.raw_record_id);
  }

  function selectedCsvRawIds() {
    const csvRows = rawRows.filter((record) => {
      const payload = mapValue(record.payload);
      const fileRef = mapValue(payload?.file_object_ref);
      return record.source_type === "file_upload" && String(fileRef?.file_name ?? "").toLowerCase().endsWith(".csv");
    });
    return csvRows.slice(0, 1).map((record) => record.raw_record_id);
  }

  function selectedXlsxRawIds() {
    const xlsxRows = rawRows.filter((record) => {
      const payload = mapValue(record.payload);
      const fileRef = mapValue(payload?.file_object_ref);
      return record.source_type === "file_upload" && String(fileRef?.file_name ?? "").toLowerCase().endsWith(".xlsx");
    });
    return xlsxRows.slice(0, 1).map((record) => record.raw_record_id);
  }

  function selectedPdfRawIds() {
    const pdfRows = rawRows.filter((record) => {
      const payload = mapValue(record.payload);
      const fileRef = mapValue(payload?.file_object_ref);
      return record.source_type === "file_upload" && String(fileRef?.file_name ?? "").toLowerCase().endsWith(".pdf");
    });
    return pdfRows.slice(0, 1).map((record) => record.raw_record_id);
  }

  function selectedDocxRawIds() {
    const docxRows = rawRows.filter((record) => {
      const payload = mapValue(record.payload);
      const fileRef = mapValue(payload?.file_object_ref);
      return record.source_type === "file_upload" && String(fileRef?.file_name ?? "").toLowerCase().endsWith(".docx");
    });
    return docxRows.slice(0, 1).map((record) => record.raw_record_id);
  }

  if (denied) {
    return (
      <StateFrame title="No permission" tone="error">
        The current user lacks data_source:read. This state is served by the backend permission API.
      </StateFrame>
    );
  }

  return (
    <div className="s1-console" data-testid="s2-source-console">
      <section className="s1-auth-strip">
        <div>
          <span className="s1-kicker">S2 Data Source Governance</span>
          <h2>Sources, Collection Runs, Raw Records</h2>
          <p>Synthetic Xi'an samples still pass through real DataSource, CollectionRun, RawRecord, Media, Lineage, audit, and PostgreSQL persistence.</p>
        </div>
        <div className="s1-permissions">
          <span>synthetic: {syntheticCount}</span>
          <span>raw: {rawRows.length}</span>
          <span>clean: {cleanRows.length}</span>
          <span>health: {health.data?.data.page_state ?? (loading ? "loading" : "unknown")}</span>
          <span>channels: {channelRows.length}</span>
          <span>adapter contract: {adapterContractData?.status ?? "loading"}</span>
          <span>maintenance: {channelMaintenanceView?.page_state ?? (channelMaintenance.isLoading ? "loading" : "unknown")}</span>
          <span>adapters: {adapterRows.length}</span>
          {degraded ? <span>degraded</span> : null}
        </div>
        <button className="admin-button secondary" type="button" onClick={refreshAll}>
          <RefreshCw size={16} />
          Refresh
        </button>
      </section>

      {loading ? <Line tone="loading" text="Loading S2 data from FastAPI." /> : null}
      {firstError ? <Line tone="error" text={firstError.message} /> : null}
      {degraded ? <Line tone="error" text="Degraded state: at least one source is blocked or health reported degraded." /> : null}

      <div className="s1-grid">
        <section className="s1-card">
          <Header icon={Database} title="Source Types And Creation" meta={types.data?.trace_id ?? "trace pending"} />
          <div className="s1-form-grid">
            <label>
              Name
              <input value={sourceName} onChange={(event) => setSourceName(event.target.value)} />
            </label>
            <label>
              Type
              <select value={sourceType} onChange={(event) => setSourceType(event.target.value)}>
                {(types.data?.data ?? []).map((item) => (
                  <option value={item.source_type} key={item.source_type}>
                    {item.source_type}
                  </option>
                ))}
              </select>
            </label>
            <button className="admin-button primary" type="button" onClick={() => createSource.mutate()} disabled={!canWrite || createSource.isPending}>
              Create Source
            </button>
            <button className="admin-button secondary" type="button" onClick={() => createBlocked.mutate()} disabled={!canWrite || createBlocked.isPending}>
              <ShieldAlert size={16} />
              Create Blocked Source
            </button>
            <label>
              Filter Type
              <select value={filterType} onChange={(event) => { setFilterType(event.target.value); setSourcePage(1); }}>
                <option value="">all</option>
                {(types.data?.data ?? []).map((item) => (
                  <option value={item.source_type} key={`filter-${item.source_type}`}>
                    {item.source_type}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Filter Status
              <select value={filterStatus} onChange={(event) => { setFilterStatus(event.target.value); setSourcePage(1); }}>
                <option value="">all</option>
                {["draft", "active", "disabled", "paused", "blocked", "archived"].map((status) => (
                  <option value={status} key={status}>
                    {status}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {createSource.isError ? <Line tone="error" text={(createSource.error as Error).message} /> : null}
          {createBlocked.isError ? <Line tone="error" text={(createBlocked.error as Error).message} /> : null}
          {channelRows.length ? <Line tone={channelWarningCount ? "error" : "empty"} text={`channels: ${channelRows.length} / warnings ${channelWarningCount} / ${channelRows.slice(0, 5).map((item) => `${item.channel}:${item.status}`).join(", ")}`} /> : null}
          {adapterContractData ? <Line tone={adapterContractData.failure_count ? "error" : "empty"} text={`adapter contract: ${adapterContractData.status} / methods ${adapterContractData.required_methods.join(", ")} / adapters ${adapterContractData.adapter_count} / degraded channels ${adapterContractData.degraded_channel_count}`} /> : null}
          {webPageQualityView ? <Line tone={webPageQualityView.page_state === "degraded" ? "error" : "empty"} text={`quality metrics: web_page runs ${Number(webPageQualityView.summary.run_count ?? 0)} / raw ${Number(webPageQualityView.summary.raw_record_count ?? 0)} / issues ${Number(webPageQualityView.summary.quality_issue_count ?? 0)} / lineage ${Number(webPageQualityView.summary.lineage_edge_count ?? 0)} / p95 ${Number(webPageQualityView.summary.p95_latency_ms ?? 0)}ms`} /> : null}
          {rssQualityView ? <Line tone={rssQualityView.page_state === "degraded" ? "error" : "empty"} text={`quality metrics: rss runs ${Number(rssQualityView.summary.run_count ?? 0)} / raw ${Number(rssQualityView.summary.raw_record_count ?? 0)} / issues ${Number(rssQualityView.summary.quality_issue_count ?? 0)} / lineage ${Number(rssQualityView.summary.lineage_edge_count ?? 0)} / p95 ${Number(rssQualityView.summary.p95_latency_ms ?? 0)}ms`} /> : null}
          {channelMaintenanceView ? <Line tone={channelMaintenanceView.page_state === "degraded" ? "error" : "empty"} text={`maintenance: ${channelMaintenanceView.page_state} / channels ${Number(channelMaintenanceView.summary.channel_count ?? 0)} / warnings ${Number(channelMaintenanceView.summary.warning_count ?? 0)} / high failure ${Number(channelMaintenanceView.summary.high_failure_channel_count ?? 0)} / missing metrics ${Number(channelMaintenanceView.summary.missing_metrics_channel_count ?? 0)} / p95 ${Number(channelMaintenanceView.summary.p95_latency_ms ?? 0)}ms`} /> : null}
          {channelMaintenanceRows.slice(0, 3).map((row) => {
            const codeVersion = mapValue(row.code_version);
            const configVersion = mapValue(row.config_version);
            const testCoverage = mapValue(row.test_coverage);
            return (
              <Line
                key={`maintenance-${stringValue(row.channel)}`}
                tone={stringValue(row.status) === "degraded" ? "error" : "empty"}
                text={`maintenance row: ${stringValue(row.channel)} failure ${Number(row.failure_rate ?? 0)} / code ${stringValue(codeVersion?.version)} / config ${String(configVersion?.latest_version ?? "none")} / tests ${stringValue(testCoverage?.status)}`}
              />
            );
          })}
          {adapterRows.length ? <Line tone="empty" text={`adapters: ${adapterRows.map((item) => item.source_type).join(", ")}`} /> : null}
          {!sourceRows.length && !loading ? <Line tone="empty" text="Empty: create a data source or generate the synthetic Xi'an sample set." /> : null}
          <div className="s1-list">
            {sourceRows.slice(0, 8).map((source) => (
              <div className="s1-row" key={source.data_source_id}>
                <b>{source.name}</b>
                <span>{source.source_type}</span>
                <button className="s2-inline-action" type="button" onClick={() => policyCheck.mutate(source.data_source_id)} disabled={!canWrite || policyCheck.isPending}>
                  {source.status}
                </button>
                <button className="s2-inline-action" type="button" onClick={() => setSelectedHealthSourceId(source.data_source_id)} disabled={!canRead || healthDetail.isFetching}>
                  Health
                </button>
                <button className="s2-inline-action" type="button" onClick={() => disableSource.mutate(source.data_source_id)} disabled={!canWrite || source.status === "disabled" || disableSource.isPending}>
                  Disable
                </button>
                <button className="s2-inline-action" type="button" onClick={() => enableSource.mutate(source.data_source_id)} disabled={!canWrite || source.status === "active" || enableSource.isPending}>
                  Enable
                </button>
              </div>
            ))}
          </div>
          <div className="s1-row-actions">
            <button className="admin-button secondary" type="button" onClick={() => setSourcePage(Math.max(1, sourcePage - 1))} disabled={sourcePage <= 1}>
              Prev
            </button>
            <span className="s2-page-indicator">page {sourcePage} / total {String(sources.data?.meta?.pagination ? (sources.data.meta.pagination as Record<string, unknown>).total : sourceRows.length)}</span>
            <button className="admin-button secondary" type="button" onClick={() => setSourcePage(sourcePage + 1)} disabled={sourceRows.length < 8}>
              Next
            </button>
          </div>
          {policyCheck.data ? <Line tone="empty" text={`policy: ${String(policyCheck.data.data.allowed)} ${policyCheck.data.data.reason ?? "allowed"}`} /> : null}
          {policyCheck.isError ? <Line tone="error" text={(policyCheck.error as Error).message} /> : null}
          {disableSource.data ? <Line tone="empty" text={`disabled: ${disableSource.data.data.name}`} /> : null}
          {enableSource.data ? <Line tone="empty" text={`enabled: ${enableSource.data.data.name}`} /> : null}
          {healthDetail.data ? (
            <Line
              tone={healthDetail.data.data.status === "healthy" ? "empty" : "error"}
              text={`health detail: ${healthDetail.data.data.status} / error_rate ${healthDetail.data.data.error_rate} / recent ${healthDetail.data.data.recent_runs.length}`}
            />
          ) : null}
          {disableSource.isError ? <Line tone="error" text={(disableSource.error as Error).message} /> : null}
          {enableSource.isError ? <Line tone="error" text={(enableSource.error as Error).message} /> : null}
          {healthDetail.isError ? <Line tone="error" text={(healthDetail.error as Error).message} /> : null}
        </section>

        <section className="s1-card">
          <Header icon={ShieldAlert} title="Public Web Validation" meta={webPageSchemaData?.version ?? validateUrl.data?.trace_id ?? "AT-035/036"} />
          <div className="s1-form-grid">
            <label>
              URL
              <input value={publicWebUrl} onChange={(event) => setPublicWebUrl(event.target.value)} />
            </label>
            <label>
              Depth
              <input value={crawlDepth} type="number" min={0} max={5} onChange={(event) => setCrawlDepth(Number(event.target.value))} />
            </label>
            <button className="admin-button secondary" type="button" onClick={() => validateUrl.mutate()} disabled={!canWrite || validateUrl.isPending}>
              Validate URL
            </button>
            <button className="admin-button primary" type="button" onClick={() => saveCrawlPolicy.mutate()} disabled={!canWrite || saveCrawlPolicy.isPending}>
              Save Crawl Policy
            </button>
            <button className="admin-button primary" type="button" onClick={() => discoverLinks.mutate()} disabled={!canWrite || discoverLinks.isPending}>
              Discover Links
            </button>
          </div>
          {validateUrl.data ? (
            <Line
              tone="empty"
              text={`url validation: ${validateUrl.data.data.reachable ? "reachable" : "blocked"} / ${validateUrl.data.data.validation_mode} / ${validateUrl.data.data.status_code ?? "no-status"}`}
            />
          ) : null}
          {saveCrawlPolicy.data ? <Line tone="empty" text={`crawl policy saved on ${saveCrawlPolicy.data.data.name}`} /> : null}
          {webPageSchemaData ? <Line tone="empty" text={`web_page schema: ${webPageSchemaData.status} / required ${webPageSchemaData.required_fields.join(", ")} / ${webPageSchemaData.workflow_refs.join(", ")}`} /> : null}
          {discoverLinks.data ? (
            <Line
              tone="empty"
              text={`link discovery: ${String(discoverLinks.data.data.activity.discovered_count ?? 0)} pending / ${String(discoverLinks.data.data.activity.skipped_count ?? 0)} skipped`}
            />
          ) : null}
          {validateUrl.isError ? <Line tone="error" text={(validateUrl.error as Error).message} /> : null}
          {saveCrawlPolicy.isError ? <Line tone="error" text={(saveCrawlPolicy.error as Error).message} /> : null}
          {discoverLinks.isError ? <Line tone="error" text={(discoverLinks.error as Error).message} /> : null}
        </section>

        <section className="s1-card">
          <Header icon={KeyRound} title="Official API Connection" meta={officialApiSchemaData?.version ?? testOfficialConnection.data?.trace_id ?? "AT-037/040"} />
          <div className="s1-form-grid">
            <label>
              Base URL
              <input value={officialApiBaseUrl} onChange={(event) => setOfficialApiBaseUrl(event.target.value)} />
            </label>
            <label>
              Secret Ref
              <input value={officialApiSecretRef} onChange={(event) => setOfficialApiSecretRef(event.target.value)} />
            </label>
            <label>
              Sample Path
              <input value={officialApiSamplePath} onChange={(event) => setOfficialApiSamplePath(event.target.value)} />
            </label>
            <label>
              Max Pages
              <input value={officialApiMaxPages} type="number" min={1} max={100} onChange={(event) => setOfficialApiMaxPages(Number(event.target.value))} />
            </label>
            <button className="admin-button secondary" type="button" onClick={() => createOfficialApi.mutate()} disabled={!canWrite || createOfficialApi.isPending}>
              Create Official API
            </button>
            <button className="admin-button secondary" type="button" onClick={() => saveOfficialAuth.mutate()} disabled={!canWrite || saveOfficialAuth.isPending}>
              Save Secret Ref
            </button>
            <button className="admin-button primary" type="button" onClick={() => testOfficialConnection.mutate()} disabled={!canWrite || testOfficialConnection.isPending}>
              Test Connection
            </button>
            <button className="admin-button secondary" type="button" onClick={() => saveOfficialCompliance.mutate()} disabled={!canWrite || saveOfficialCompliance.isPending}>
              Save Compliance
            </button>
            <button className="admin-button primary" type="button" onClick={() => publishOfficialVersion.mutate()} disabled={!canWrite || publishOfficialVersion.isPending}>
              Publish Source Version
            </button>
            <button className="admin-button secondary" type="button" onClick={() => rollbackOfficialVersion.mutate()} disabled={!canWrite || rollbackOfficialVersion.isPending}>
              Rollback To V1
            </button>
            <button className="admin-button secondary" type="button" onClick={() => createOnceJob.mutate()} disabled={!canWrite || createOnceJob.isPending}>
              Create Once Job
            </button>
            <button className="admin-button secondary" type="button" onClick={() => createCronJob.mutate()} disabled={!canWrite || createCronJob.isPending}>
              Create Cron Job
            </button>
            <button className="admin-button secondary" type="button" onClick={() => saveOfficialPagination.mutate()} disabled={!canWrite || saveOfficialPagination.isPending}>
              Save Pagination
            </button>
          </div>
          {createOfficialApi.data ? <Line tone="empty" text={`official source ready: ${String(createOfficialApi.data.name)}`} /> : null}
          {officialApiSchemaData ? <Line tone="empty" text={`official_api schema: ${officialApiSchemaData.status} / required ${officialApiSchemaData.required_fields.join(", ")} / ${String(officialApiSchemaData.validation.plain_secret_fields_allowed) === "false" ? "secret_ref only" : "secret policy pending"}`} /> : null}
          {saveOfficialAuth.data ? <Line tone="empty" text={`auth saved: ${String(saveOfficialAuth.data.data.status)} ${String((saveOfficialAuth.data.data.policy.policy_result as { reason?: string } | undefined)?.reason ?? "allowed")}`} /> : null}
          {testOfficialConnection.data ? (
            <Line
              tone="empty"
              text={`connection: ${testOfficialConnection.data.data.status} / ${testOfficialConnection.data.data.classification} / ${String(testOfficialConnection.data.data.status_code ?? "no-status")}`}
            />
          ) : null}
          {saveOfficialCompliance.data ? <Line tone="empty" text={`compliance: ${String((saveOfficialCompliance.data.data.policy.policy_result as { compliance_ready?: boolean } | undefined)?.compliance_ready ?? false)}`} /> : null}
          {publishOfficialVersion.data ? <Line tone="empty" text={`version: v${publishOfficialVersion.data.data.version} / ${publishOfficialVersion.data.data.status}`} /> : null}
          {rollbackOfficialVersion.data ? <Line tone="empty" text={`rollback: v${String(rollbackOfficialVersion.data.data.payload.rollback_from_version ?? "?")} -> v${String(rollbackOfficialVersion.data.data.payload.rollback_to_version ?? "?")} as v${rollbackOfficialVersion.data.data.version}`} /> : null}
          {createOnceJob.data ? <Line tone="empty" text={`once job: ${String(createOnceJob.data.data.schedule)} / ${String((createOnceJob.data.data.payload as { data_source_version?: number } | undefined)?.data_source_version ?? "no-version")}`} /> : null}
          {createCronJob.data ? <Line tone="empty" text={`cron job: ${String(createCronJob.data.data.schedule)} / ${String(((createCronJob.data.data.payload as { scheduler_registration?: { status?: string } } | undefined)?.scheduler_registration?.status) ?? "not-registered")}`} /> : null}
          {saveOfficialPagination.data ? <Line tone="empty" text={`pagination: ${String((saveOfficialPagination.data.data.policy.pagination as { strategy?: string } | undefined)?.strategy ?? "saved")}`} /> : null}
          {[createOfficialApi, saveOfficialAuth, testOfficialConnection, saveOfficialCompliance, publishOfficialVersion, rollbackOfficialVersion, createOnceJob, createCronJob, saveOfficialPagination].map((mutation, index) =>
            mutation.isError ? <Line key={index} tone="error" text={(mutation.error as Error).message} /> : null
          )}
        </section>

        <section className="s1-card">
          <Header icon={Database} title="Collection Jobs" meta={`AT-058 / total ${String(jobPagination?.total ?? jobRows.length)}`} />
          <div className="s1-form-grid">
            <label>
              Status
              <select
                value={jobStatusFilter}
                onChange={(event) => {
                  setJobPage(1);
                  setJobStatusFilter(event.target.value);
                }}
              >
                <option value="">all</option>
                {["active", "blocked", "paused", "archived", "completed"].map((status) => (
                  <option value={status} key={status}>
                    {status}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Source ID
              <input
                value={jobSourceFilter}
                onChange={(event) => {
                  setJobPage(1);
                  setJobSourceFilter(event.target.value.trim());
                }}
                placeholder="DS-..."
              />
            </label>
            <label>
              Creator ID
              <input
                value={jobCreatorFilter}
                onChange={(event) => {
                  setJobPage(1);
                  setJobCreatorFilter(event.target.value.trim());
                }}
                placeholder="USR-..."
              />
            </label>
            <button className="admin-button secondary" type="button" onClick={() => createRateLimitJobs.mutate()} disabled={!canWrite || createRateLimitJobs.isPending}>
              <Gauge size={16} />
              Create Rate Limit Jobs
            </button>
            <button className="admin-button primary" type="button" onClick={() => runRateLimitTwice.mutate()} disabled={!canWrite || runRateLimitTwice.isPending}>
              <Play size={16} />
              Run Rate Limit Twice
            </button>
            <button className="admin-button secondary" type="button" onClick={() => loadRateLimitStats.mutate()} disabled={!canRead || loadRateLimitStats.isPending || !rateLimitSourceId}>
              Load Rate Limit Stats
            </button>
          </div>
          {collectionJobs.isFetching ? <Line tone="loading" text="Loading collection jobs from API." /> : null}
          {!jobRows.length && !collectionJobs.isFetching ? <Line tone="empty" text="Empty: no collection jobs match the current filters." /> : null}
          <div className="s1-list">
            {jobRows.map((job) => (
              <div className="s1-row s2-job-row" key={job.collection_job_id}>
                <b>{job.name}</b>
                <span>{job.status}</span>
                <span>{job.schedule ?? "manual"}</span>
                <span>{job.data_source_id}</span>
                <small>{job.created_by_id ?? "system"}</small>
                <button className="s2-inline-action" type="button" onClick={() => startJobRun.mutate(job.collection_job_id)} disabled={!canWrite || startJobRun.isPending}>
                  Run
                </button>
                <button className="s2-inline-action" type="button" onClick={() => pauseJob.mutate(job.collection_job_id)} disabled={!canWrite || pauseJob.isPending || job.status === "paused"}>
                  <Pause size={12} />
                  Pause
                </button>
                <button className="s2-inline-action" type="button" onClick={() => resumeJob.mutate(job.collection_job_id)} disabled={!canWrite || resumeJob.isPending || job.status !== "paused"}>
                  <RotateCcw size={12} />
                  Resume
                </button>
                <button className="s2-inline-action" type="button" onClick={() => setSelectedJobId(job.collection_job_id)} disabled={collectionJobDetail.isFetching}>
                  Detail
                </button>
              </div>
            ))}
          </div>
          {jobDetailData ? (
            <div className="s2-detail-panel">
              <Line tone="empty" text={`detail: ${jobDetailData.name} / ${jobDetailData.page_state} / runs ${String(jobDetailData.run_summary.total_runs ?? 0)}`} />
              <Line tone="empty" text={`version: ${String(jobDetailData.version_pin.data_source_version ?? "no-version")} / latest ${String(jobDetailData.run_summary.latest_status ?? "no-runs")}`} />
              <Line tone="empty" text={`config: ${String(jobDetailData.config.job_kind ?? "manual")} / ${String(jobDetailData.config.schedule ?? jobDetailData.schedule ?? "no-schedule")}`} />
              {(jobDetailData.latest_runs ?? []).slice(0, 3).map((run) => {
                const runId = String(run.collection_run_id ?? "");
                const runStatus = String(run.status ?? "unknown");
                return (
                  <div className="s2-run-action-row" key={runId}>
                    <span>{runId}</span>
                    <b>{runStatus}</b>
                    <button className="s2-inline-action" type="button" onClick={() => setSelectedRunId(runId)} disabled={!canRead || collectionRunSteps.isFetching}>
                      Steps
                    </button>
                    <button className="s2-inline-action" type="button" onClick={() => cancelRun.mutate(runId)} disabled={!canWrite || cancelRun.isPending || !["pending", "running", "retrying", "delayed", "cancelling"].includes(runStatus)}>
                      Cancel
                    </button>
                    <button className="s2-inline-action" type="button" onClick={() => retryRun.mutate(runId)} disabled={!canWrite || retryRun.isPending || !["failed", "canceled"].includes(runStatus)}>
                      Retry
                    </button>
                  </div>
                );
              })}
            </div>
          ) : null}
          {startJobRun.data ? <Line tone="empty" text={`run started: ${String(startJobRun.data.data.status)} / ${String((startJobRun.data.data.payload as { workflow_status?: string } | undefined)?.workflow_status ?? "no-workflow")}`} /> : null}
          {createRateLimitJobs.data ? <Line tone="empty" text={`rate limit jobs: ${createRateLimitJobs.data.dataSourceId} / ${createRateLimitJobs.data.jobIds.length} jobs`} /> : null}
          {runRateLimitTwice.data ? <Line tone="empty" text={`channel rate limit run: web ${String(runRateLimitTwice.data.first.status)} -> ${String(runRateLimitTwice.data.second.status)} / rss ${String(runRateLimitTwice.data.rss.status)} / web delayed ${String(runRateLimitTwice.data.stats.state.delayed_count ?? 0)} / rss delayed ${String(runRateLimitTwice.data.rssStats.state.delayed_count ?? 0)}`} /> : null}
          {rateLimitView ? <Line tone={rateLimitView.status === "limited" ? "error" : "empty"} text={`rate limit stats: ${rateLimitView.status} / channel ${String(rateLimitView.channel ?? "all")} / jobs ${String(rateLimitJobIds.length)} / used ${String(rateLimitView.state.used ?? 0)} / delayed ${String(rateLimitView.state.delayed_count ?? 0)} / next ${String(rateLimitView.state.next_allowed_at ?? "available")}`} /> : null}
          {runRateLimitTwice.data?.aggregateStats?.channel_states ? <Line tone="empty" text={`channel states: web_page used ${String(runRateLimitTwice.data.aggregateStats.channel_states.web_page?.used ?? 0)} delayed ${String(runRateLimitTwice.data.aggregateStats.channel_states.web_page?.delayed_count ?? 0)} / rss used ${String(runRateLimitTwice.data.aggregateStats.channel_states.rss?.used ?? 0)} delayed ${String(runRateLimitTwice.data.aggregateStats.channel_states.rss?.delayed_count ?? 0)}`} /> : null}
          {pauseJob.data ? <Line tone="empty" text={`job paused: ${pauseJob.data.data.status} / ${String((pauseJob.data.data.payload.pause as { active_run_count?: number } | undefined)?.active_run_count ?? 0)} active runs preserved`} /> : null}
          {resumeJob.data ? <Line tone="empty" text={`job resumed: ${resumeJob.data.data.status} / ${String((resumeJob.data.data.payload.resume as { scheduler_state?: string } | undefined)?.scheduler_state ?? "ready")}`} /> : null}
          {cancelRun.data ? <Line tone="empty" text={`run canceled: ${String(cancelRun.data.data.status)} / ${String((cancelRun.data.data.payload as { workflow_status?: string } | undefined)?.workflow_status ?? "no-workflow")}`} /> : null}
          {retryRun.data ? <Line tone="empty" text={`run retry: ${String(retryRun.data.data.status)} / ${String((retryRun.data.data.payload as { workflow_status?: string } | undefined)?.workflow_status ?? "no-workflow")}`} /> : null}
          {startJobRun.isError ? <Line tone="error" text={(startJobRun.error as Error).message} /> : null}
          {createRateLimitJobs.isError ? <Line tone="error" text={(createRateLimitJobs.error as Error).message} /> : null}
          {runRateLimitTwice.isError ? <Line tone="error" text={(runRateLimitTwice.error as Error).message} /> : null}
          {loadRateLimitStats.isError ? <Line tone="error" text={(loadRateLimitStats.error as Error).message} /> : null}
          {pauseJob.isError ? <Line tone="error" text={(pauseJob.error as Error).message} /> : null}
          {resumeJob.isError ? <Line tone="error" text={(resumeJob.error as Error).message} /> : null}
          {cancelRun.isError ? <Line tone="error" text={(cancelRun.error as Error).message} /> : null}
          {retryRun.isError ? <Line tone="error" text={(retryRun.error as Error).message} /> : null}
          <div className="s2-pagination">
            <button className="admin-button secondary" type="button" onClick={() => setJobPage(Math.max(1, jobPage - 1))} disabled={jobPage <= 1}>
              Prev Jobs
            </button>
            <span className="s2-page-indicator">page {String(jobPagination?.page ?? jobPage)} / total {String(jobPagination?.total ?? jobRows.length)}</span>
            <button className="admin-button secondary" type="button" onClick={() => setJobPage(jobPage + 1)} disabled={jobRows.length < 8}>
              Next Jobs
            </button>
          </div>
        </section>

        <section className="s1-card s1-wide">
          <Header icon={Play} title="Collection Runs" meta={`AT-065 / total ${String(runPagination?.total ?? runRows.length)}`} />
          <div className="s1-form-grid">
            <label>
              Status
              <select
                value={runStatusFilter}
                onChange={(event) => {
                  setRunPage(1);
                  setRunStatusFilter(event.target.value);
                }}
              >
                <option value="">all</option>
                {["pending", "running", "retrying", "delayed", "cancelling", "failed", "completed", "canceled"].map((status) => (
                  <option value={status} key={status}>
                    {status}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Source ID
              <input
                value={runSourceFilter}
                onChange={(event) => {
                  setRunPage(1);
                  setRunSourceFilter(event.target.value.trim());
                }}
                placeholder="DS-..."
              />
            </label>
            <label>
              Job ID
              <input
                value={runJobFilter}
                onChange={(event) => {
                  setRunPage(1);
                  setRunJobFilter(event.target.value.trim());
                }}
                placeholder="CJOB-..."
              />
            </label>
            <label>
              From
              <input
                value={runCreatedFromFilter}
                onChange={(event) => {
                  setRunPage(1);
                  setRunCreatedFromFilter(event.target.value.trim());
                }}
                placeholder="2026-05-09T00:00:00"
              />
            </label>
            <label>
              To
              <input
                value={runCreatedToFilter}
                onChange={(event) => {
                  setRunPage(1);
                  setRunCreatedToFilter(event.target.value.trim());
                }}
                placeholder="2026-05-10T00:00:00"
              />
            </label>
          </div>
          {collectionRuns.isFetching ? <Line tone="loading" text="Loading collection runs from API." /> : null}
          {!runRows.length && !collectionRuns.isFetching ? <Line tone="empty" text="Empty: no collection runs match the current filters." /> : null}
          <div className="s1-table s2-run-list">
            {runRows.map((run) => {
              const canCancel = ["pending", "running", "retrying", "delayed", "cancelling"].includes(run.status);
              const canRetry = ["failed", "canceled"].includes(run.status);
              return (
                <div className="s2-run-list-row" key={run.collection_run_id}>
                  <b>{run.collection_run_id}</b>
                  <span>{run.status}</span>
                  <span>{run.data_source_id}</span>
                  <span>{run.collection_job_id}</span>
                  <small>{run.created_at}</small>
                  <small>{run.trace_id ?? "no-trace"}</small>
                  <button className="s2-inline-action" type="button" onClick={() => cancelRun.mutate(run.collection_run_id)} disabled={!canWrite || cancelRun.isPending || !canCancel}>
                    Cancel
                  </button>
                  <button className="s2-inline-action" type="button" onClick={() => retryRun.mutate(run.collection_run_id)} disabled={!canWrite || retryRun.isPending || !canRetry}>
                    Retry
                  </button>
                  <button className="s2-inline-action" type="button" onClick={() => setSelectedRunId(run.collection_run_id)} disabled={!canRead || collectionRunSteps.isFetching}>
                    Steps
                  </button>
                  <button className="s2-inline-action" type="button" onClick={() => setSelectedRunId(run.collection_run_id)} disabled={!canRead || collectionRunMetrics.isFetching}>
                    Metrics
                  </button>
                </div>
              );
            })}
          </div>
          {selectedRunId ? (
            <div className="s2-detail-panel">
              {collectionRunSteps.isFetching ? <Line tone="loading" text={`Refreshing steps for ${selectedRunId}.`} /> : null}
              {collectionRunSteps.isError ? <Line tone="error" text={(collectionRunSteps.error as Error).message} /> : null}
              {collectionRunMetrics.isFetching ? <Line tone="loading" text={`Refreshing metrics for ${selectedRunId}.`} /> : null}
              {collectionRunMetrics.isError ? <Line tone="error" text={(collectionRunMetrics.error as Error).message} /> : null}
              {runStepsData ? (
                <>
                  <Line tone="empty" text={`steps: ${runStepsData.collection_run_id} / ${runStepsData.status} / workflow ${runStepsData.workflow_status ?? "none"} / raw ${runStepsData.raw_record_count}`} />
                  {selectedRunRecord?.error_code ? (
                    <Line
                      tone={!selectedRunError?.known || selectedRunError?.severity === "error" || selectedRunError?.severity === "critical" ? "error" : "empty"}
                      text={`run error: ${String(selectedRunError?.channel ?? "unknown")} / ${String(selectedRunError?.error_code ?? selectedRunRecord.error_code)} / ${String(selectedRunError?.label ?? "unmapped")} / ${String(selectedRunError?.run_detail_hint ?? selectedRunRecord.error_message ?? "inspect run payload")}`}
                    />
                  ) : null}
                  {runMetricData ? (
                    <Line
                      tone={runMetricData.consistency.status === "consistent" ? "empty" : "error"}
                      text={`metrics: parsed ${runMetricData.metrics.parsed_count} / cleaned ${runMetricData.metrics.cleaned_count} / extracted ${runMetricData.metrics.extracted_count} / failed ${runMetricData.metrics.failed_count} / ${runMetricData.consistency.status}`}
                    />
                  ) : null}
                  <div className="s2-step-strip">
                    {runStepsData.steps.map((step) => (
                      <div className={`s2-step-pill ${step.status}`} key={step.step_key}>
                        <b>{step.label}</b>
                        <span>{step.status}</span>
                        <small>{step.event_count} events</small>
                      </div>
                    ))}
                  </div>
                  {runMetricData ? (
                    <div className="s1-list">
                      <div className="s1-row">
                        <b>stored</b>
                        <span>{runMetricData.metrics.stored_count} raw / {runMetricData.metrics.payload_count} payloads</span>
                        <small>{runMetricData.metrics.lineage_edge_count} lineage</small>
                      </div>
                      <div className="s1-row">
                        <b>clean/extract</b>
                        <span>{runMetricData.metrics.normalization_output_count} clean outputs / {runMetricData.metrics.signal_count} signals</span>
                        <small>{runMetricData.cleaning_run_id}</small>
                      </div>
                      <div className="s1-row">
                        <b>consistency</b>
                        <span>{runMetricData.consistency.checks.filter((check) => check.passed).length} checks passed</span>
                        <small>{String(runMetricData.snapshot.metric_scope ?? "snapshot")}</small>
                      </div>
                    </div>
                  ) : null}
                  <div className="s1-list">
                    {runStepsData.events.slice(0, 5).map((event) => (
                      <div className="s1-row" key={String(event.event_id)}>
                        <b>{String(event.event_type)}</b>
                        <span>{String(event.status)}</span>
                        <small>{String(event.step_key ?? event.source ?? "run")}</small>
                      </div>
                    ))}
                  </div>
                </>
              ) : null}
            </div>
          ) : null}
          <div className="s2-pagination">
            <button className="admin-button secondary" type="button" onClick={() => setRunPage(Math.max(1, runPage - 1))} disabled={runPage <= 1}>
              Prev Runs
            </button>
            <span className="s2-page-indicator">page {String(runPagination?.page ?? runPage)} / total {String(runPagination?.total ?? runRows.length)}</span>
            <button className="admin-button secondary" type="button" onClick={() => setRunPage(runPage + 1)} disabled={runRows.length < 8}>
              Next Runs
            </button>
          </div>
        </section>

        <section className="s1-card">
          <Header icon={FileText} title="RSS Feed Inspect" meta={inspectRss.data?.trace_id ?? "AT-041/042"} />
          <div className="s1-form-grid">
            <label>
              Feed URL
              <input value={rssFeedUrl} onChange={(event) => setRssFeedUrl(event.target.value)} />
            </label>
            <button className="admin-button secondary" type="button" onClick={() => createRssSource.mutate()} disabled={!canWrite || createRssSource.isPending}>
              Create RSS Source
            </button>
            <button className="admin-button primary" type="button" onClick={() => inspectRss.mutate()} disabled={!canWrite || inspectRss.isPending}>
              Inspect RSS
            </button>
            <button className="admin-button secondary" type="button" onClick={() => fetchRssItems.mutate()} disabled={!canWrite || fetchRssItems.isPending}>
              Fetch RSS Items
            </button>
          </div>
          {createRssSource.data ? <Line tone="empty" text={`rss source ready: ${String(createRssSource.data.name)}`} /> : null}
          {inspectRss.data ? (
            <Line
              tone="empty"
              text={`rss: ${inspectRss.data.data.title ?? "untitled"} / ${inspectRss.data.data.item_count} items / ${inspectRss.data.data.latest_time ?? "no-latest-time"}`}
            />
          ) : null}
          {rssFetchRun ? (
            <Line
              tone={String(rssFetchRun.status) === "completed" ? "empty" : "error"}
              text={`rss fetch: ${String(rssFetchRun.status ?? "unknown")} / ${String(rssFetchActivity?.item_count ?? 0)} items / ${String(rssFetchActivity?.new_record_count ?? rssFetchRun.record_count ?? 0)} new / ${String(rssFetchActivity?.duplicate_count ?? 0)} dup`}
            />
          ) : null}
          {createRssSource.isError ? <Line tone="error" text={(createRssSource.error as Error).message} /> : null}
          {inspectRss.isError ? <Line tone="error" text={(inspectRss.error as Error).message} /> : null}
          {fetchRssItems.isError ? <Line tone="error" text={(fetchRssItems.error as Error).message} /> : null}
        </section>

        <section className="s1-card">
          <Header icon={FileText} title="File Upload Source" meta={documentFileSchemaData?.version ?? startUploadedFileRun.data?.trace_id ?? receiveFileUpload.data?.trace_id ?? "AT-043/071/072"} />
          <div className="s1-form-grid">
            <button className="admin-button secondary" type="button" onClick={() => createFileUploadSource.mutate()} disabled={!canWrite || !documentSchemaReady || createFileUploadSource.isPending}>
              Create File Upload Source
            </button>
            <label>
              Upload file
              <input
                type="file"
                accept={documentFileAccept}
                onChange={(event) => setSelectedUploadFile(event.target.files?.[0] ?? null)}
                disabled={!canWrite || !documentSchemaReady || receiveFileUpload.isPending || startUploadedFileRun.isPending}
              />
            </label>
            <button className="admin-button primary" type="button" onClick={() => receiveFileUpload.mutate()} disabled={!canWrite || !documentSchemaReady || !selectedUploadFile || receiveFileUpload.isPending}>
              Upload File
            </button>
            <button className="admin-button primary" type="button" onClick={() => startUploadedFileRun.mutate()} disabled={!canWrite || !documentSchemaReady || !uploadedFileObjectId || startUploadedFileRun.isPending}>
              Import Uploaded File
            </button>
          </div>
          {createFileUploadSource.data ? (
            <Line
              tone="empty"
              text={`file upload source: ${createFileUploadSource.data.status} / ${(createFileUploadSource.data.policy.allowed_file_types as string[] | undefined)?.join(",") ?? "no-types"}`}
            />
          ) : null}
          {documentFileSchemaData ? (
            <Line
              tone="empty"
              text={`document_file schema: ${documentFileSchemaData.status} / allowed ${documentAllowedTypes.join(", ")} / mapping ${documentFileSchemaData.required_fields.join(", ")}`}
            />
          ) : null}
          {selectedUploadFile ? <Line tone="loading" text={`selected upload: ${selectedUploadFile.name} / ${selectedUploadFile.size} bytes`} /> : null}
          {receiveFileUpload.data ? (
            <Line
              tone="empty"
              text={`upload: ${String((receiveFileUpload.data.data.upload as JsonMap | undefined)?.status ?? "unknown")} / ${String((receiveFileUpload.data.data.file_object as JsonMap | undefined)?.file_name ?? "file")} / ${String((receiveFileUpload.data.data.upload as JsonMap | undefined)?.byte_size ?? 0)} bytes`}
            />
          ) : null}
          {uploadedFileObjectId ? <Line tone="empty" text={`uploaded file object: ${uploadedFileObjectId}`} /> : null}
          {startUploadedFileRun.isPending ? <Line tone="loading" text="Importing uploaded file through collection job file-run API." /> : null}
          {startUploadedFileRun.data ? (
            <Line
              tone={String(fileImportRun?.status ?? fileCollectionRun?.status ?? "unknown") === "completed" ? "empty" : "loading"}
              text={`file import: ${String(fileImportRun?.status ?? "unknown")} / run ${String(fileCollectionRun?.collection_run_id ?? "pending")} / raw ${String(fileImportRun?.record_count ?? fileRawRecords.length)}`}
            />
          ) : null}
          {createFileUploadSource.isError ? <Line tone="error" text={(createFileUploadSource.error as Error).message} /> : null}
          {receiveFileUpload.isError ? <Line tone="error" text={(receiveFileUpload.error as Error).message} /> : null}
          {startUploadedFileRun.isError ? <Line tone="error" text={(startUploadedFileRun.error as Error).message} /> : null}
        </section>

        <section className="s1-card">
          <Header icon={KeyRound} title="Webhook Signature" meta={sendWebhookPayload.data?.trace_id ?? "AT-044/045"} />
          <div className="s1-form-grid">
            <button className="admin-button secondary" type="button" onClick={() => createWebhookSource.mutate()} disabled={!canWrite || createWebhookSource.isPending}>
              Create Webhook Source
            </button>
            <button className="admin-button primary" type="button" onClick={() => sendWebhookPayload.mutate()} disabled={!canWrite || !webhookSourceKey || sendWebhookPayload.isPending}>
              Send Signed Webhook
            </button>
          </div>
          {createWebhookSource.data ? <Line tone="empty" text={`webhook: ${webhookEndpoint} / key ${webhookSourceKey}`} /> : null}
          {sendWebhookPayload.data ? <Line tone="empty" text={`webhook received: ${String(sendWebhookPayload.data.data.raw_record ? (sendWebhookPayload.data.data.raw_record as { raw_record_id?: string }).raw_record_id : "raw-record-created")}`} /> : null}
          {createWebhookSource.isError ? <Line tone="error" text={(createWebhookSource.error as Error).message} /> : null}
          {sendWebhookPayload.isError ? <Line tone="error" text={(sendWebhookPayload.error as Error).message} /> : null}
        </section>

        <section className="s1-card">
          <Header icon={FileText} title="Manual Source" meta={createManualRecord.data?.trace_id ?? createManualSource.data?.trace_id ?? "AT-046/074/092"} />
          <div className="s1-form-grid">
            <label>
              Title
              <input value={manualTitle} onChange={(event) => setManualTitle(event.target.value)} />
            </label>
            <label>
              Content
              <textarea value={manualContent} onChange={(event) => setManualContent(event.target.value)} />
            </label>
            <label>
              Time
              <input value={manualOccurredAt} onChange={(event) => setManualOccurredAt(event.target.value)} />
            </label>
            <label>
              Location
              <input value={manualLocation} onChange={(event) => setManualLocation(event.target.value)} />
            </label>
            <label className="s1-check">
              <input type="checkbox" checked={manualIsSynthetic} onChange={(event) => setManualIsSynthetic(event.target.checked)} />
              Synthetic
            </label>
            <button className="admin-button secondary" type="button" onClick={() => createManualSource.mutate()} disabled={!canWrite || createManualSource.isPending}>
              Create Manual Source
            </button>
            <button
              className="admin-button primary"
              type="button"
              onClick={() => createManualRecord.mutate()}
              disabled={!canWrite || createManualRecord.isPending}
            >
              Create Manual Record
            </button>
          </div>
          {createManualSource.data ? <Line tone="empty" text={`manual source: ${createManualSource.data.data.status} / ${String((createManualSource.data.data.policy.entry_schema as { city_id?: string } | undefined)?.city_id ?? "no-city")}`} /> : null}
          {createManualRecord.data ? (
            <Line
              tone={String(manualRecordRun?.status ?? "unknown") === "completed" ? "empty" : "loading"}
              text={`manual record: ${String(manualRecordRaw?.status ?? "unknown")} / validation ${String(manualRecordValidation?.status ?? "pending")} / clean ${String(manualRecordCleanDraftPayload?.clean_record_status ?? "pending")} / raw ${String(manualRecordRaw?.raw_record_id ?? "pending")}`}
            />
          ) : null}
          {createManualSource.isError ? <Line tone="error" text={(createManualSource.error as Error).message} /> : null}
          {createManualRecord.isError ? <Line tone="error" text={(createManualRecord.error as Error).message} /> : null}
        </section>

        <section className="s1-card">
          <Header icon={Database} title="DB And Object Sources" meta={listObjectStorage.data?.trace_id ?? "AT-047/048"} />
          <div className="s1-form-grid">
            <label>
              DB Table
              <input value={dbImportTableName} onChange={(event) => setDbImportTableName(event.target.value)} />
            </label>
            <label>
              Scan Limit
              <input
                min={1}
                max={100000}
                type="number"
                value={dbImportLimit}
                onChange={(event) => setDbImportLimit(Math.max(1, Math.min(100000, Number(event.target.value) || 1)))}
              />
            </label>
            <button className="admin-button secondary" type="button" onClick={() => createDbImportSource.mutate()} disabled={!canWrite || createDbImportSource.isPending}>
              Create DB Import
            </button>
            <button className="admin-button primary" type="button" onClick={() => testDbImportConnection.mutate()} disabled={!canWrite || testDbImportConnection.isPending}>
              Test DB Import
            </button>
            <button className="admin-button primary" type="button" onClick={() => scanDbImportTable.mutate()} disabled={!canWrite || scanDbImportTable.isPending || !dbImportTableName.trim()}>
              Scan DB Table
            </button>
            <button className="admin-button secondary" type="button" onClick={() => loadDbCursorState.mutate()} disabled={!canRead || loadDbCursorState.isPending}>
              Load Cursor State
            </button>
            <label>
              Object Prefix
              <input value={objectStoragePrefix} onChange={(event) => setObjectStoragePrefix(event.target.value)} />
            </label>
            <label>
              Object Limit
              <input
                min={1}
                max={10000}
                type="number"
                value={objectStorageScanLimit}
                onChange={(event) => setObjectStorageScanLimit(Math.max(1, Math.min(10000, Number(event.target.value) || 1)))}
              />
            </label>
            <button className="admin-button secondary" type="button" onClick={() => createObjectStorageSource.mutate()} disabled={!canWrite || createObjectStorageSource.isPending}>
              Create Object Storage
            </button>
            <button className="admin-button primary" type="button" onClick={() => listObjectStorage.mutate()} disabled={!canWrite || listObjectStorage.isPending}>
              List Object Keys
            </button>
            <button className="admin-button primary" type="button" onClick={() => scanObjectStoragePrefix.mutate()} disabled={!canWrite || scanObjectStoragePrefix.isPending || !objectStoragePrefix.trim()}>
              Scan Object Prefix
            </button>
          </div>
          {createDbImportSource.data ? <Line tone="empty" text={`db import: ${createDbImportSource.data.data.status}`} /> : null}
          {testDbImportConnection.data ? <Line tone="empty" text={`db test: ${testDbImportConnection.data.data.status} / ${String(testDbImportConnection.data.data.sample_metadata.row_count ?? "no-rows")} rows`} /> : null}
          {scanDbImportTable.data ? (
            <Line
              tone={String(dbScanRun?.status ?? "unknown") === "completed" ? "empty" : "error"}
              text={`db scan: ${String(dbScanRun?.status ?? "unknown")} / ${String(dbScanActivity?.row_count ?? dbScanRun?.record_count ?? 0)} rows / cursor ${String(dbScanActivity?.next_cursor ?? "pending")}`}
            />
          ) : null}
          {loadDbCursorState.data ? (
            <Line
              tone={loadDbCursorState.data.data.page_state === "ready" ? "empty" : "loading"}
              text={`cursor state: ${loadDbCursorState.data.data.page_state} / ${String(dbCursor?.table_key ?? "no-table")}/${String(dbCursor?.cursor_field ?? "no-field")} ${String(dbCursor?.current_value ?? 0)} / guard ${String(dbCursorGuard?.failed_runs_do_not_advance_cursor ?? false)}`}
            />
          ) : null}
          {createObjectStorageSource.data ? <Line tone="empty" text={`object storage: ${createObjectStorageSource.data.data.status}`} /> : null}
          {listObjectStorage.data ? <Line tone="empty" text={`object keys: ${String(listObjectStorage.data.data.key_count ?? 0)}`} /> : null}
          {scanObjectStoragePrefix.data ? (
            <Line
              tone={String(objectScanRun?.status ?? "unknown") === "completed" ? "empty" : "error"}
              text={`object scan: ${String(objectScanRun?.status ?? "unknown")} / ${String(objectScanActivity?.new_record_count ?? objectScanRun?.record_count ?? 0)} files / missing ${String(objectScanActivity?.missing_count ?? 0)}`}
            />
          ) : null}
          {[createDbImportSource, testDbImportConnection, scanDbImportTable, loadDbCursorState, createObjectStorageSource, listObjectStorage, scanObjectStoragePrefix].map((mutation, index) =>
            mutation.isError ? <Line key={index} tone="error" text={(mutation.error as Error).message} /> : null
          )}
        </section>

        <section className="s1-card">
          <Header icon={Play} title="Synthetic Xi'an Collection" meta="real collection chain" />
          <button className="admin-button primary" type="button" onClick={() => generateSynthetic.mutate()} disabled={!canWrite || generateSynthetic.isPending}>
            <Play size={16} />
            Generate Synthetic Samples
          </button>
          {generateSynthetic.isError ? <Line tone="error" text={(generateSynthetic.error as Error).message} /> : null}
          {generateSynthetic.data ? (
            <Line tone="empty" text={`run ${String(generateSynthetic.data.data.collection_run.collection_run_id)} created ${generateSynthetic.data.data.raw_records.length} raw records`} />
          ) : null}
          {!healthRows.length && !loading ? <Line tone="empty" text="Empty: source health will appear after source creation or collection." /> : null}
          <div className="s1-list">
            {healthRows.slice(0, 6).map((item) => (
              <div className="s1-row" key={String(item.source_health_id)}>
                <b>{String(item.data_source_id)}</b>
                <span>{String(item.status)}</span>
                <small>{String(item.success_count ?? 0)} ok</small>
              </div>
            ))}
          </div>
        </section>

        <section className="s1-card s1-wide">
          <Header icon={ShieldAlert} title="Imports And Processing Runs" meta="file/web/api/media + normalize/dedup/quality" />
          <div className="s1-row-actions">
            <button className="admin-button secondary" type="button" onClick={() => importFile.mutate()} disabled={!canWrite || importFile.isPending}>
              Import File
            </button>
            <button className="admin-button secondary" type="button" onClick={() => importPublicWeb.mutate()} disabled={!canWrite || importPublicWeb.isPending}>
              Import Web
            </button>
            <button className="admin-button secondary" type="button" onClick={() => importMedia.mutate()} disabled={!canWrite || !imageSchemaReady || importMedia.isPending}>
              Import Media
            </button>
            <button className="admin-button secondary" type="button" onClick={() => importVideoMedia.mutate()} disabled={!canWrite || !videoSchemaReady || importVideoMedia.isPending}>
              Import Video
            </button>
            <button className="admin-button secondary" type="button" onClick={() => importLiveSegment.mutate()} disabled={!canWrite || !livestreamSchemaReady || importLiveSegment.isPending}>
              Import Live
            </button>
            <button className="admin-button secondary" type="button" onClick={() => importAudioMedia.mutate()} disabled={!canWrite || !audioSchemaReady || importAudioMedia.isPending}>
              Import Audio
            </button>
            <button className="admin-button secondary" type="button" onClick={() => importOfficialApi.mutate()} disabled={!canWrite || importOfficialApi.isPending}>
              Official API Failure
            </button>
            <button className="admin-button secondary" type="button" onClick={() => fetchOfficialApi.mutate()} disabled={!canWrite || fetchOfficialApi.isPending}>
              Fetch Official API
            </button>
            <button className="admin-button primary" type="button" onClick={() => runRetryBackoffProbe.mutate()} disabled={!canWrite || runRetryBackoffProbe.isPending}>
              Run Retry Backoff
            </button>
            <button className="admin-button primary" type="button" onClick={() => replayDeadLetter.mutate()} disabled={!canWrite || replayDeadLetter.isPending}>
              Replay Dead Letter
            </button>
            <button className="admin-button primary" type="button" onClick={() => replayChannelCheckpoint.mutate()} disabled={!canWrite || replayChannelCheckpoint.isPending}>
              Replay Channel Checkpoint
            </button>
            <button className="admin-button primary" type="button" onClick={() => runNormalization.mutate()} disabled={!canWrite || rawRows.length === 0 || runNormalization.isPending}>
              Normalize Text
            </button>
            <button className="admin-button primary" type="button" onClick={() => runDatetimeNormalization.mutate()} disabled={!canWrite || rawRows.length === 0 || runDatetimeNormalization.isPending}>
              Normalize Time
            </button>
            <button className="admin-button primary" type="button" onClick={() => runLocationNormalization.mutate()} disabled={!canWrite || rawRows.length === 0 || runLocationNormalization.isPending}>
              Normalize Location
            </button>
            <button className="admin-button primary" type="button" onClick={() => runSourceTrustAssignment.mutate()} disabled={!canWrite || rawRows.length === 0 || runSourceTrustAssignment.isPending}>
              Assign Trust
            </button>
            <button className="admin-button primary" type="button" onClick={() => runSensitiveFieldDetection.mutate()} disabled={!canWrite || rawRows.length === 0 || runSensitiveFieldDetection.isPending}>
              Detect Sensitive
            </button>
            <button className="admin-button primary" type="button" onClick={() => runSensitiveFieldRedaction.mutate()} disabled={!canWrite || rawRows.length === 0 || runSensitiveFieldRedaction.isPending}>
              Redact Sensitive
            </button>
            <button className="admin-button primary" type="button" onClick={() => runHtmlParser.mutate()} disabled={!canWrite || rawRows.length === 0 || runHtmlParser.isPending}>
              Parse HTML
            </button>
            <button className="admin-button primary" type="button" onClick={() => runJsonParser.mutate()} disabled={!canWrite || rawRows.length === 0 || runJsonParser.isPending}>
              Parse JSON
            </button>
            <button className="admin-button primary" type="button" onClick={() => runRssParser.mutate()} disabled={!canWrite || selectedRssRawIds().length === 0 || runRssParser.isPending}>
              Parse RSS Items
            </button>
            <button className="admin-button primary" type="button" onClick={() => runCsvParser.mutate()} disabled={!canWrite || selectedCsvRawIds().length === 0 || runCsvParser.isPending}>
              Parse CSV
            </button>
            <button className="admin-button primary" type="button" onClick={() => runXlsxParser.mutate()} disabled={!canWrite || selectedXlsxRawIds().length === 0 || runXlsxParser.isPending}>
              Parse XLSX
            </button>
            <button className="admin-button primary" type="button" onClick={() => runPdfParser.mutate()} disabled={!canWrite || selectedPdfRawIds().length === 0 || runPdfParser.isPending}>
              Parse PDF
            </button>
            <button className="admin-button primary" type="button" onClick={() => runDocxParser.mutate()} disabled={!canWrite || selectedDocxRawIds().length === 0 || runDocxParser.isPending}>
              Parse DOCX
            </button>
            <button className="admin-button primary" type="button" onClick={() => runDeduplication.mutate()} disabled={!canWrite || rawRows.length === 0 || runDeduplication.isPending}>
              Dedup
            </button>
            <button className="admin-button primary" type="button" onClick={() => runSemanticDeduplication.mutate()} disabled={!canWrite || rawRows.length === 0 || runSemanticDeduplication.isPending}>
              Semantic Dedupe
            </button>
            <button className="admin-button secondary" type="button" onClick={() => confirmDedupeCandidate.mutate()} disabled={!canWrite || !semanticDecisionTarget() || confirmDedupeCandidate.isPending}>
              Confirm Dedupe
            </button>
            <button className="admin-button secondary" type="button" onClick={() => splitDedupeCandidate.mutate()} disabled={!canWrite || !semanticDecisionTarget() || splitDedupeCandidate.isPending}>
              Split Candidate
            </button>
            <button className="admin-button primary" type="button" onClick={() => runQuality.mutate()} disabled={!canWrite || selectedQualityRawIds().length === 0 || runQuality.isPending}>
              Quality
            </button>
          </div>
          {[importFile, importPublicWeb, importMedia, importVideoMedia, importLiveSegment, importAudioMedia, importOfficialApi, fetchOfficialApi, runRetryBackoffProbe, replayDeadLetter, replayChannelCheckpoint, runNormalization, runDatetimeNormalization, runLocationNormalization, runSourceTrustAssignment, runSensitiveFieldDetection, runSensitiveFieldRedaction, runHtmlParser, runJsonParser, runRssParser, runCsvParser, runXlsxParser, runPdfParser, runDocxParser, runDeduplication, runSemanticDeduplication, confirmDedupeCandidate, splitDedupeCandidate, runQuality].map((mutation, index) =>
            mutation.isError ? <Line key={index} tone="error" text={(mutation.error as Error).message} /> : null
          )}
          {importWebRun ? (
            <Line
              tone={String(importWebRun.status) === "completed" ? "empty" : "error"}
              text={`web fetch: ${String(importWebRun.status ?? "unknown")} / ${String(importWebActivity?.classification ?? importWebRun.error_code ?? "pending")} / ${String(importWebRun.record_count ?? 0)} raw`}
            />
          ) : null}
          {officialApiRun ? (
            <Line
              tone={String(officialApiRun.status) === "completed" ? "empty" : "error"}
              text={`official fetch: ${String(officialApiRun.status ?? "unknown")} / ${String(officialApiActivity?.classification ?? officialApiRun.error_code ?? "pending")} / ${String(officialApiRun.record_count ?? 0)} raw / ${String(officialApiActivity?.page_count ?? 0)} pages`}
            />
          ) : null}
          {runRetryBackoffProbe.data ? (
            <Line
              tone="empty"
              text={`retry backoff: ${String(retryBackoffRows.length)} scheduled / delays ${retryBackoffDelays || "none"} / permanent ${String(mapValue(retryBackoffPermanent)?.classification ?? "none")}`}
            />
          ) : null}
          {runRetryBackoffProbe.data ? (
            <Line
              tone="empty"
              text={`dead letters: ${String(retryBackoffDeadLetters.length)} open / ${String(retryBackoffDeadLetters[0]?.error_code ?? "none")}`}
            />
          ) : null}
          {replayDeadLetter.data ? (
            <Line
              tone={String(replayDeadLetterData?.status ?? "unknown") === "completed" || String(replayDeadLetterData?.status ?? "unknown") === "already_completed" ? "empty" : "error"}
              text={`dead letter replay: ${String(replayDeadLetterData?.status ?? "unknown")} / raw ${String(replayDeadLetterImport?.record_count ?? 0)}`}
            />
          ) : null}
          {channelReplayRun ? (
            <Line
              tone={String(channelReplayRun.status ?? "unknown") === "pending" ? "empty" : "error"}
              text={`channel replay: ${String(channelReplayRun.status ?? "unknown")} / ${String(channelReplayPayload?.collection_channel ?? "no-channel")} / checkpoint ${String(channelReplayCheckpoint?.checkpoint_id ?? "missing")} / skip raw ${String(channelReplayGuard?.skip_existing_raw ?? false)}`}
            />
          ) : null}
          {normalizationData ? (
            <Line
              tone={String(normalizationData.status ?? "unknown") === "completed" && Number(normalizationSummary?.valid_count ?? 0) > 0 ? "empty" : "error"}
              text={`normalize text: valid ${String(normalizationSummary?.valid_count ?? 0)} / invalid ${String(normalizationSummary?.invalid_count ?? 0)} / ${String(normalizationOutputs[0]?.normalized_text ?? normalizationData.error_code ?? "no output")}`}
            />
          ) : null}
          {datetimeNormalizationData ? (
            <Line
              tone={String(datetimeNormalizationData.status ?? "unknown") === "completed" && Number(datetimeNormalizationSummary?.normalized_count ?? 0) > 0 ? "empty" : "error"}
              text={`normalize time: normalized ${String(datetimeNormalizationSummary?.normalized_count ?? 0)} / review ${String(datetimeNormalizationSummary?.review_required_count ?? 0)} / ${String(mapValue(datetimeNormalizationOutputs[0]?.payload)?.normalized_datetime_utc ?? datetimeNormalizationData.error_code ?? "no time")}`}
            />
          ) : null}
          {locationNormalizationData ? (
            <Line
              tone={String(locationNormalizationData.status ?? "unknown") === "completed" && Number(locationNormalizationSummary?.normalized_count ?? 0) > 0 ? "empty" : "error"}
              text={`normalize location: normalized ${String(locationNormalizationSummary?.normalized_count ?? 0)} / candidates ${String(locationNormalizationSummary?.candidate_count ?? 0)} / ${String(mapValue(locationNormalizationOutputs[0]?.payload)?.district ?? mapValue(locationNormalizationOutputs[0]?.payload)?.city ?? locationNormalizationData.error_code ?? "no location")}`}
            />
          ) : null}
          {sourceTrustData ? (
            <Line
              tone={String(sourceTrustData.status ?? "unknown") === "completed" && Number(sourceTrustSummary?.output_count ?? 0) > 0 ? "empty" : "error"}
              text={`source trust: assigned ${String(sourceTrustSummary?.assigned_count ?? 0)} / defaulted ${String(sourceTrustSummary?.defaulted_count ?? 0)} / score ${String(mapValue(sourceTrustOutputs[0]?.payload)?.trust_score ?? sourceTrustData.error_code ?? "no score")}`}
            />
          ) : null}
          {sensitiveDetectionData ? (
            <Line
              tone={String(sensitiveDetectionData.status ?? "unknown") === "completed" ? "empty" : "error"}
              text={`sensitive detect: records ${String(sensitiveDetectionSummary?.detected_record_count ?? 0)} / fields ${String(sensitiveDetectionSummary?.sensitive_count ?? 0)} / ${sensitiveDetectionTypes.join(",") || "clean"}`}
            />
          ) : null}
          {sensitiveRedactionData ? (
            <Line
              tone={String(sensitiveRedactionData.status ?? "unknown") === "completed" ? "empty" : "error"}
              text={`sensitive redact: records ${String(sensitiveRedactionSummary?.redacted_record_count ?? 0)} / fields ${String(sensitiveRedactionSummary?.sensitive_count ?? 0)} / ${sensitiveRedactionTypes.join(",") || "clean"}`}
            />
          ) : null}
          {deduplicationData ? (
            <Line
              tone={String(deduplicationData.status ?? "unknown") === "completed" ? "empty" : "error"}
              text={`rule dedupe: groups ${String(deduplicationSummary?.duplicate_group_count ?? 0)} / dup ${String(deduplicationSummary?.duplicate_record_count ?? 0)} / cross-source candidates ${String(deduplicationSummary?.cross_source_candidate_count ?? 0)}`}
            />
          ) : null}
          {semanticDeduplicationData ? (
            <Line
              tone={["completed", "partial"].includes(String(semanticDeduplicationData.status ?? "unknown")) ? "empty" : "error"}
              text={`semantic dedupe: candidates ${String(semanticDeduplicationSummary?.candidate_group_count ?? 0)} / records ${String(semanticDeduplicationSummary?.candidate_record_count ?? 0)} / embedding failed ${String(semanticDeduplicationSummary?.embedding_failed_count ?? 0)}`}
            />
          ) : null}
          {semanticDecisionData ? (
            <Line
              tone={["confirmed_duplicate", "split_candidate"].includes(String(semanticDecision?.status ?? "unknown")) ? "empty" : "error"}
              text={`dedupe decision: ${String(semanticDecision?.status ?? "unknown")} / group ${String(semanticDecisionData.dedup_group_id ?? semanticDecision?.dedup_group_id ?? "none")} / duplicate_of ${String(semanticDecision?.duplicate_of_raw_record_id ?? "none")}`}
            />
          ) : null}
          {qualityData ? (
            <Line
              tone={String(qualityData.status ?? "unknown") === "completed" ? "empty" : "error"}
              text={`quality score: avg ${String(qualitySummary?.average_overall ?? 0)} / scored ${String(qualitySummary?.score_count ?? 0)} / issues ${String(qualitySummary?.issue_count ?? qualityData.issue_count ?? 0)}`}
            />
          ) : null}
          {htmlParserData ? (
            <Line
              tone={String(htmlParserData.status ?? "unknown") === "completed" && Number(htmlParserSummary?.parsed_count ?? 0) > 0 ? "empty" : "error"}
              text={`html parse: parsed ${String(htmlParserSummary?.parsed_count ?? 0)} / failed ${String(htmlParserSummary?.failed_count ?? 0)} / ${String(htmlParserOutputs[0]?.normalized_title ?? "no title")}`}
            />
          ) : null}
          {jsonParserData ? (
            <Line
              tone={String(jsonParserData.status ?? "unknown") === "completed" && Number(jsonParserSummary?.parsed_count ?? 0) > 0 ? "empty" : "error"}
              text={`json parse: parsed ${String(jsonParserSummary?.parsed_count ?? 0)} / failed ${String(jsonParserSummary?.failed_count ?? 0)} / ${String(jsonParserOutputs[0]?.normalized_title ?? "no title")}`}
            />
          ) : null}
          {imageFileSchemaData ? (
            <Line
              tone="empty"
              text={`image_file schema: ${imageFileSchemaData.status} / formats ${imageAllowedFormats.join(", ")} / ${String(imageFileSchemaData.validation.redaction_required) === "true" ? "redaction required" : "redaction warning"}`}
            />
          ) : null}
          {videoFileSchemaData ? (
            <Line
              tone="empty"
              text={`video_file schema: ${videoFileSchemaData.status} / formats ${videoAllowedFormats.join(", ")} / large policy ${String(videoFileSchemaData.validation.large_video_policy_missing_code ?? "pending")}`}
            />
          ) : null}
          {livestreamSchemaData ? (
            <Line
              tone="empty"
              text={`livestream schema: ${livestreamSchemaData.status} / protocol ${String(livestreamProtocolDefault ?? "pending")} / retention ${String(livestreamSchemaData.validation.retention_policy_missing_code ?? "pending")}`}
            />
          ) : null}
          {audioFileSchemaData ? (
            <Line
              tone="empty"
              text={`audio_file schema: ${audioFileSchemaData.status} / formats ${audioAllowedFormats.join(", ")} / languages ${stringArrayValue(audioFileSchemaData.validation.supported_languages).join(", ") || "pending"}`}
            />
          ) : null}
          {channelErrorMap ? (
            <Line
              tone={channelErrorMap.status === "ready" && channelErrorMap.summary.warning_count === 0 ? "empty" : "error"}
              text={`channel error map: ${channelErrorMap.status} / registered ${String(channelErrorMap.summary.registered_mapping_count)} / channels ${String(channelErrorMap.summary.channel_count)} / unmapped ${String(channelErrorMap.summary.unknown_count)}`}
            />
          ) : null}
          <Line
            tone="empty"
            text={`json mapping: title ${String(jsonMapping.title ?? "$.title")} / body ${String(jsonMapping.body ?? "$.summary")} / time ${String(jsonMapping.published_at ?? "$.published_at")}`}
          />
          {rssParserData ? (
            <Line
              tone={String(rssParserData.status ?? "unknown") === "completed" && Number(rssParserSummary?.parsed_count ?? 0) > 0 ? "empty" : "error"}
              text={`rss parse: items ${String(rssParserSummary?.item_count ?? 0)} / parsed ${String(rssParserSummary?.parsed_count ?? 0)} / dup ${String(rssParserSummary?.duplicate_count ?? 0)} / ${String(rssParserOutputs[0]?.normalized_title ?? rssParserData.error_code ?? "no item")}`}
            />
          ) : null}
          {csvParserData ? (
            <Line
              tone={String(csvParserData.status ?? "unknown") === "completed" && Number(csvParserSummary?.parsed_count ?? 0) > 0 ? "empty" : "error"}
              text={`csv parse: rows ${String(csvParserSummary?.row_count ?? 0)} / parsed ${String(csvParserSummary?.parsed_count ?? 0)} / failed ${String(csvParserSummary?.failed_count ?? 0)} / ${String(csvParserOutputs[0]?.normalized_title ?? csvParserData.error_code ?? "no row")}`}
            />
          ) : null}
          <Line
            tone="empty"
            text={`csv mapping: title ${String(csvMapping.title ?? "title")} / body ${String(csvMapping.body ?? "content")} / time ${String(csvMapping.published_at ?? "published_at")}`}
          />
          {xlsxParserData ? (
            <Line
              tone={String(xlsxParserData.status ?? "unknown") === "completed" && Number(xlsxParserSummary?.parsed_count ?? 0) > 0 ? "empty" : "error"}
              text={`xlsx parse: ${String(xlsxParserSummary?.sheet_name ?? "sheet")} ${String(xlsxParserSummary?.cell_range ?? "range")} / rows ${String(xlsxParserSummary?.row_count ?? 0)} / parsed ${String(xlsxParserSummary?.parsed_count ?? 0)} / ${String(xlsxParserOutputs[0]?.normalized_title ?? xlsxParserData.error_code ?? "no row")}`}
            />
          ) : null}
          <Line
            tone="empty"
            text={`xlsx mapping: title ${String(xlsxMapping.title ?? "title")} / body ${String(xlsxMapping.body ?? "content")} / time ${String(xlsxMapping.published_at ?? "published_at")}`}
          />
          {pdfParserData ? (
            <Line
              tone={String(pdfParserData.status ?? "unknown") === "completed" && Number(pdfParserSummary?.parsed_count ?? 0) > 0 ? "empty" : "error"}
              text={`pdf parse: pages ${String(pdfParserSummary?.page_count ?? 0)} / parsed ${String(pdfParserSummary?.parsed_count ?? 0)} / ocr ${String(pdfParserSummary?.ocr_required_count ?? 0)} / ${String(pdfParserOutputs[0]?.normalized_title ?? pdfParserData.error_code ?? "no page")}`}
            />
          ) : null}
          {docxParserData ? (
            <Line
              tone={String(docxParserData.status ?? "unknown") === "completed" && Number(docxParserSummary?.block_count ?? 0) > 0 ? "empty" : "error"}
              text={`docx parse: blocks ${String(docxParserSummary?.block_count ?? 0)} / paragraphs ${String(docxParserSummary?.paragraph_count ?? 0)} / table cells ${String(docxParserSummary?.table_cell_count ?? 0)} / ${String(docxParserOutputs[0]?.normalized_title ?? docxParserData.error_code ?? "no block")}`}
            />
          ) : null}
          {firstImportRunError ? (
            <Line
              tone={!firstImportRunError.known || firstImportRunError.severity === "error" || firstImportRunError.severity === "critical" ? "error" : "empty"}
              text={`import error mapped: ${firstImportRunError.channel} / ${firstImportRunError.error_code} / ${firstImportRunError.label} / ${firstImportRunError.remediation}`}
            />
          ) : null}
          {firstDeadLetterError ? (
            <Line
              tone={!firstDeadLetterError.known || firstDeadLetterError.severity === "error" || firstDeadLetterError.severity === "critical" ? "error" : "empty"}
              text={`dead letter mapped: ${firstDeadLetterError.channel} / ${firstDeadLetterError.error_code} / ${firstDeadLetterError.classification} / ${firstDeadLetterError.run_detail_hint}`}
            />
          ) : null}
          <div className="s2-run-grid">
            <RunColumn title="Import runs" rows={importRuns.data?.data ?? []} idKey="import_run_id" valueKey="record_count" />
            <RunColumn title="Dead letters" rows={deadLetterRows} idKey="dead_letter_id" valueKey="error_code" />
            <RunColumn title="Normalization" rows={normalizationRuns.data?.data ?? []} idKey="normalization_run_id" valueKey="output_count" />
            <RunColumn title="Dedup" rows={deduplicationRuns.data?.data ?? []} idKey="deduplication_run_id" valueKey="duplicate_group_count" />
            <RunColumn title="Quality" rows={qualityRuns.data?.data ?? []} idKey="data_quality_run_id" valueKey="issue_count" />
          </div>
        </section>

        <section className="s1-card s1-wide">
          <Header icon={ShieldAlert} title="Data Quality Issues" meta={qualityIssues.data?.trace_id ?? "trace pending"} />
          <div className="s1-form-grid">
            <label>
              Issue Type
              <input value={qualityIssueTypeFilter} onChange={(event) => { setQualityIssueTypeFilter(event.target.value); setQualityIssuePage(1); }} placeholder="missing_city" />
            </label>
            <label>
              Severity
              <select value={qualityIssueSeverityFilter} onChange={(event) => { setQualityIssueSeverityFilter(event.target.value); setQualityIssuePage(1); }}>
                <option value="">all</option>
                <option value="info">info</option>
                <option value="warning">warning</option>
                <option value="error">error</option>
                <option value="critical">critical</option>
              </select>
            </label>
            <button
              className="admin-button secondary"
              type="button"
              onClick={() => {
                setQualityIssueTypeFilter("");
                setQualityIssueSeverityFilter("");
                setQualityIssuePage(1);
              }}
            >
              Clear Issue Filters
            </button>
          </div>
          {qualityIssues.isFetching ? <Line tone="loading" text="Loading data quality issues from FastAPI." /> : null}
          {qualityIssues.isError ? <Line tone="error" text={(qualityIssues.error as Error).message} /> : null}
          {qualityIssues.data ? (
            <Line
              tone="empty"
              text={`quality issues: ${qualityIssueState} / returned ${qualityIssueRows.length} / total ${String(qualityIssuePagination?.total ?? qualityIssueRows.length)} / types ${Object.keys(mapValue(qualityIssueSummary?.issue_type_counts) ?? {}).length}`}
            />
          ) : null}
          {!qualityIssueRows.length && !qualityIssues.isFetching && !qualityIssues.isError ? <Line tone="empty" text="Empty: no quality issues match the current filters." /> : null}
          <div className="s1-table">
            {qualityIssueRows.map((issue) => {
              const rawRecord = mapValue(issue.raw_record) ?? {};
              const qualityScore = typeof issue.quality_score === "number" ? `q ${issue.quality_score.toFixed(2)}` : "q -";
              return (
                <button
                  className="s2-run-list-row s2-quality-issue-row"
                  key={issue.quality_issue_id}
                  type="button"
                  onClick={() => {
                    const rawRecordId = String(issue.raw_record_id ?? rawRecord.raw_record_id ?? "");
                    setSelectedCleanRecordId(rawRecordId);
                    setLastLineageRawId(rawRecordId);
                  }}
                >
                  <b>{issue.issue_type}</b>
                  <span>{issue.severity}</span>
                  <span>{String(rawRecord.source_type ?? "unknown")}</span>
                  <span>{qualityScore}</span>
                  <span>{String(rawRecord.title ?? issue.raw_record_id).slice(0, 46)}</span>
                  <small>{issue.message}</small>
                </button>
              );
            })}
          </div>
          <div className="s1-row-actions">
            <button className="admin-button secondary" type="button" onClick={() => setQualityIssuePage(Math.max(1, qualityIssuePage - 1))} disabled={qualityIssuePage <= 1}>
              Prev Issues
            </button>
            <span className="s2-page-indicator">page {qualityIssuePage} / total {String(qualityIssuePagination?.total ?? qualityIssueRows.length)}</span>
            <button className="admin-button secondary" type="button" onClick={() => setQualityIssuePage(qualityIssuePage + 1)} disabled={qualityIssueRows.length < 8}>
              Next Issues
            </button>
          </div>
        </section>

        <section className="s1-card s1-wide">
          <Header icon={ListFilter} title="Clean Records" meta={cleanRecords.data?.trace_id ?? "trace pending"} />
          <div className="s1-form-grid">
            <label>
              Status
              <select value={cleanStatusFilter} onChange={(event) => { setCleanStatusFilter(event.target.value); setCleanPage(1); }}>
                <option value="">all</option>
                {CLEAN_RECORD_STATUSES.map((status) => (
                  <option value={status} key={status}>
                    {status}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Data Source
              <input value={cleanSourceFilter} onChange={(event) => { setCleanSourceFilter(event.target.value); setCleanPage(1); }} placeholder="data_source_id" />
            </label>
            <label>
              Source Type
              <select value={cleanTypeFilter} onChange={(event) => { setCleanTypeFilter(event.target.value); setCleanPage(1); }}>
                <option value="">all</option>
                {(types.data?.data ?? []).map((item) => (
                  <option value={item.source_type} key={`clean-type-${item.source_type}`}>
                    {item.source_type}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Created From
              <input value={cleanCreatedFromFilter} onChange={(event) => { setCleanCreatedFromFilter(event.target.value); setCleanPage(1); }} placeholder="2026-05-01T00:00:00Z" />
            </label>
            <label>
              Created To
              <input value={cleanCreatedToFilter} onChange={(event) => { setCleanCreatedToFilter(event.target.value); setCleanPage(1); }} placeholder="2026-05-10T00:00:00Z" />
            </label>
            <button
              className="admin-button secondary"
              type="button"
              onClick={() => {
                setCleanStatusFilter("");
                setCleanSourceFilter("");
                setCleanTypeFilter("");
                setCleanCreatedFromFilter("");
                setCleanCreatedToFilter("");
                setCleanPage(1);
              }}
            >
              Clear Filters
            </button>
          </div>
          {cleanRecords.isFetching ? <Line tone="loading" text="Loading clean records from FastAPI." /> : null}
          {cleanRecords.isError ? <Line tone="error" text={(cleanRecords.error as Error).message} /> : null}
          {cleanRecords.data ? <Line tone="empty" text={`clean page: ${cleanPageState} / returned ${cleanRows.length} / total ${String(cleanPagination?.total ?? cleanRows.length)}`} /> : null}
          {!cleanRows.length && !cleanRecords.isFetching && !cleanRecords.isError ? <Line tone="empty" text="Empty: no clean records match the current filters." /> : null}
          <div className="s1-table">
            {cleanRows.map((record) => (
              <button
                className="s2-raw-row s2-clean-row"
                key={record.clean_record_id}
                type="button"
                onClick={() => {
                  setSelectedCleanRecordId(record.clean_record_id);
                  setLastLineageRawId(record.raw_record_id);
                }}
              >
                <b>{record.title}</b>
                <span>{record.clean_status}</span>
                <span>{record.source_type}</span>
                <span>{typeof record.quality_score === "number" ? `q ${record.quality_score.toFixed(2)}` : "q -"}</span>
                <span>{record.review_required ? "review" : record.content_redacted ? "redacted" : "open"}</span>
                <span>{String(record.masked_text_preview ?? "").slice(0, 72)}</span>
              </button>
            ))}
          </div>
          <div className="s1-row-actions">
            <button className="admin-button secondary" type="button" onClick={() => setCleanPage(Math.max(1, cleanPage - 1))} disabled={cleanPage <= 1}>
              Prev
            </button>
            <span className="s2-page-indicator">page {cleanPage} / total {String(cleanPagination?.total ?? cleanRows.length)}</span>
            <button className="admin-button secondary" type="button" onClick={() => setCleanPage(cleanPage + 1)} disabled={cleanRows.length < 8}>
              Next
            </button>
          </div>
          {!selectedCleanRecordId ? <Line tone="empty" text="Empty: select a clean record to load raw, clean, extraction, quality, and lineage detail." /> : null}
          {cleanRecordDetail.isFetching ? <Line tone="loading" text={`Loading clean detail for ${selectedCleanRecordId}.`} /> : null}
          {cleanRecordDetail.isError ? <Line tone="error" text={(cleanRecordDetail.error as Error).message} /> : null}
          {cleanDetailData ? (
            <div className="s1-list">
              <div className="s1-row">
                <b>detail: {cleanDetailData.clean_record_id}</b>
                <span>{String(cleanDetailData.clean.status ?? cleanDetailData.clean_record.clean_status)}</span>
                <small>{String(cleanDetailData.page_state ?? "ready")}</small>
              </div>
              <div className="s1-row">
                <b>raw masked</b>
                <span>{String(cleanDetailData.raw.masked_text ?? "").slice(0, 140)}</span>
                <small>{String(cleanDetailData.access.access_mode ?? "redacted")}</small>
              </div>
              <div className="s1-row">
                <b>clean text</b>
                <span>{String(cleanDetailLatest?.normalized_text_preview ?? cleanDetailLatest?.normalized_text ?? "no normalization").slice(0, 140)}</span>
                <small>{String(cleanDetailData.clean.normalization_count ?? 0)} outputs</small>
              </div>
              <div className="s1-row">
                <b>quality</b>
                <span>{cleanDetailIssues.map((issue) => String(issue.issue_type ?? "issue")).join(", ") || "no issues"}</span>
                <small>{String(cleanDetailData.quality.quality_score ?? cleanDetailData.clean_record.quality_score ?? cleanDetailData.quality.issue_count ?? 0)}</small>
              </div>
              <div className="s1-row">
                <b>extraction</b>
                <span>{cleanDetailSignals.map((signal) => String(signal.title ?? signal.signal_id ?? "signal")).join(", ") || "no signals"}</span>
                <small>{String(cleanDetailData.extractions.signal_count ?? 0)}</small>
              </div>
              <div className="s1-row">
                <b>lineage</b>
                <span>{cleanDetailEdges.slice(0, 4).map((edge) => `${String(edge.from_object_type)}->${String(edge.to_object_type)}`).join(", ") || "no lineage"}</span>
                <small>{String(cleanDetailData.lineage.edge_count ?? 0)}</small>
              </div>
            </div>
          ) : null}
          {cleanDetailData ? (
            <div className="s1-row-actions">
              <button className="admin-button secondary" type="button" onClick={() => updateCleanRecordStatus.mutate({ status: "valid", reason: "AT-112 marked valid from S2 console." })} disabled={!canWrite || updateCleanRecordStatus.isPending}>
                Mark Valid
              </button>
              <button className="admin-button secondary" type="button" onClick={() => updateCleanRecordStatus.mutate({ status: "review_required", reason: "AT-112 marked review_required from S2 console." })} disabled={!canWrite || updateCleanRecordStatus.isPending}>
                Mark Review
              </button>
              <button className="admin-button secondary" type="button" onClick={() => updateCleanRecordStatus.mutate({ status: "invalid", reason: "AT-112 marked invalid from S2 console." })} disabled={!canWrite || updateCleanRecordStatus.isPending}>
                Mark Invalid
              </button>
            </div>
          ) : null}
          {updateCleanRecordStatus.data ? (
            <Line
              tone={String(updateCleanRecordStatus.data.data.status_transition?.status ?? "unknown") === "invalid" ? "loading" : "empty"}
              text={`status update: ${String(updateCleanRecordStatus.data.data.status_transition?.previous_status ?? "unknown")} -> ${String(updateCleanRecordStatus.data.data.status_transition?.status ?? "unknown")} / signal allowed ${String(updateCleanRecordStatus.data.data.downstream_effect?.signal_generation_allowed ?? true)}`}
            />
          ) : null}
          {updateCleanRecordStatus.isError ? <Line tone="error" text={(updateCleanRecordStatus.error as Error).message} /> : null}
        </section>

        <section className="s1-card s1-wide">
          <Header icon={FileText} title="Raw Records And Lineage" meta={rawRecords.data?.trace_id ?? "trace pending"} />
          <div className="s1-row-actions">
            <button className="admin-button primary" type="button" onClick={() => createRawRepositoryBatch.mutate()} disabled={!canWrite || createRawRepositoryBatch.isPending}>
              Repository Smoke
            </button>
            <button className="admin-button primary" type="button" onClick={() => runRawHashDedupe.mutate()} disabled={!canWrite || runRawHashDedupe.isPending}>
              Dedupe Smoke
            </button>
            <button className="admin-button secondary" type="button" onClick={() => exportSelectedRawRecord.mutate()} disabled={!canRead || !lastLineageRawId || exportSelectedRawRecord.isPending}>
              Export Redacted
            </button>
          </div>
          {createRawRepositoryBatch.data ? (
            <Line
              tone={String(rawRepositoryData?.status ?? "unknown") === "stored" ? "empty" : "error"}
              text={`repository store: ${String(rawRepositoryData?.status ?? "unknown")} / ${String(rawRepositoryData?.stored_count ?? 0)} raw / run ${String(rawRepositoryRun?.status ?? "pending")}`}
            />
          ) : null}
          {createRawRepositoryBatch.isError ? <Line tone="error" text={(createRawRepositoryBatch.error as Error).message} /> : null}
          {runRawHashDedupe.data ? (
            <Line
              tone={Number(rawHashConflictRepo?.conflict_count ?? 0) === 1 && Number(rawHashDuplicateRepo?.duplicate_count ?? 0) === 1 ? "empty" : "error"}
              text={`raw hash dedupe: ${String(rawHashDuplicateRepo?.duplicate_count ?? 0)} duplicate / ${String(rawHashConflictRepo?.conflict_count ?? 0)} conflict / hit ${String(rawHashDuplicateRepo?.dedupe_hit_rate ?? 0)}`}
            />
          ) : null}
          {runRawHashDedupe.isError ? <Line tone="error" text={(runRawHashDedupe.error as Error).message} /> : null}
          {exportSelectedRawRecord.data ? (
            <Line tone="empty" text={`redacted export: ${String(exportSelectedRawRecord.data.data.access_mode ?? "redacted")} / ${String(exportSelectedRawRecord.data.data.content_redacted ?? true)} / ${String(exportSelectedRawRecord.data.data.format ?? "text/plain")}`} />
          ) : null}
          {exportSelectedRawRecord.isError ? <Line tone="error" text={(exportSelectedRawRecord.error as Error).message} /> : null}
          {!rawRows.length && !loading ? <Line tone="empty" text="Empty: no raw records yet. Generate the synthetic Xi'an sample set first." /> : null}
          <div className="s1-table">
            {rawRows.slice(0, 12).map((record) => (
              <button className="s2-raw-row" key={record.raw_record_id} type="button" onClick={() => setLastLineageRawId(record.raw_record_id)}>
                <b>{record.title}</b>
                <span>{record.source_type}</span>
                <span>{record.is_synthetic ? "synthetic" : "real"}</span>
                <span>{record.content_hash.slice(0, 18)}</span>
              </button>
            ))}
          </div>
          {lastLineageRawId ? <Line tone="empty" text={`lineage selected: ${lastLineageRawId}`} /> : null}
          {rawDetail.data ? (
            <Line
              tone={rawDetail.data.data.access_mode === "redacted" && rawDetail.data.data.content_redacted === true ? "empty" : "error"}
              text={`masked detail: ${String(rawDetail.data.data.access_mode ?? "unknown")} / ${String(rawDetail.data.data.content_redacted ?? false)} / ${String(rawDetail.data.data.masked_text ?? "").slice(0, 120)}`}
            />
          ) : null}
          <div className="s1-list">
            {(lineage.data?.data ?? []).slice(0, 8).map((edge) => (
              <div className="s1-row" key={String(edge.lineage_edge_id)}>
                <b>
                  {String(edge.from_object_type)} {"->"} {String(edge.to_object_type)}
                </b>
                <span>{String(edge.relation)}</span>
                <small>{String(edge.is_synthetic)}</small>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

function Header({ icon: Icon, title, meta }: { icon: LucideIcon; title: string; meta: string }) {
  return (
    <header className="s1-card-title">
      <span>
        <Icon size={16} />
        {title}
      </span>
      <small>{meta}</small>
    </header>
  );
}

function RunColumn({ title, rows, idKey, valueKey }: { title: string; rows: Array<Record<string, unknown>>; idKey: string; valueKey: string }) {
  return (
    <div className="s2-run-column">
      <b>{title}</b>
      {rows.slice(0, 4).map((row) => (
        <span key={String(row[idKey])}>
          {String(row.status ?? "unknown")} / {String(row[valueKey] ?? row.error_code ?? 0)}
        </span>
      ))}
      {!rows.length ? <span>empty</span> : null}
    </div>
  );
}

function StateFrame({ title, tone, children }: { title: string; tone: LineTone; children: ReactNode }) {
  return (
    <div className="s1-console" data-testid="s2-source-console">
      <section className="s1-card">
        <Header icon={ShieldAlert} title={title} meta={tone} />
        <Line tone={tone} text={String(children)} />
      </section>
    </div>
  );
}

function Line({ tone, text }: { tone: LineTone; text: string }) {
  return <p className={`s1-line ${tone}`}>{text}</p>;
}

function mapValue(value: unknown): JsonMap | undefined {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as JsonMap) : undefined;
}

function stringArrayValue(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value : "";
}
