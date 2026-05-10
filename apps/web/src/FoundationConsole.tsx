import { AlertTriangle, CheckCircle2, Database, FileCheck2, Lock, LogOut, Play, RefreshCw, ShieldCheck, Users } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, getAuthToken, ReviewRecord, setAuthToken } from "./api";

export type S1ConsoleMode = "foundation" | "reviews" | "ops";

export function S1FoundationConsole({ mode }: { mode: S1ConsoleMode }) {
  const queryClient = useQueryClient();
  const [token, setToken] = useState(() => getAuthToken() ?? "");
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin12345");

  useEffect(() => {
    setAuthToken(token || null);
  }, [token]);

  const meQuery = useQuery({
    queryKey: ["s1-auth-me", token],
    queryFn: api.me,
    enabled: Boolean(token),
    retry: false
  });
  const navigationQuery = useQuery({
    queryKey: ["s1-navigation", token],
    queryFn: api.navigation,
    enabled: Boolean(token) && meQuery.isSuccess,
    retry: false
  });

  const login = useMutation({
    mutationFn: () => api.login(username, password),
    onSuccess: async (result) => {
      setToken(result.data.access_token);
      await queryClient.invalidateQueries({ queryKey: ["s1-auth-me"] });
    }
  });

  const logout = useMutation({
    mutationFn: api.logout,
    onSettled: async () => {
      setToken("");
      setAuthToken(null);
      await queryClient.invalidateQueries();
    }
  });

  if (!token || meQuery.isError) {
    return (
      <div className="s1-console" data-testid="s1-login-panel">
        <section className="s1-login">
          <div>
            <span className="s1-kicker">S1 Foundation</span>
            <h2>登录生产控制台</h2>
            <p>登录、权限、审计、Review 和 Ops Health 均通过 FastAPI 和数据库记录驱动。</p>
          </div>
          <label>
            账号
            <input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" />
          </label>
          <label>
            密码
            <input value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" type="password" />
          </label>
          <button className="admin-button primary" type="button" disabled={login.isPending} onClick={() => login.mutate()}>
            <Lock size={16} />
            {login.isPending ? "登录中" : "登录"}
          </button>
          {login.isError ? <StateLine tone="error" text={(login.error as Error).message} /> : null}
          {meQuery.isError && token ? <StateLine tone="error" text={(meQuery.error as Error).message} /> : null}
          <StateLine tone="empty" text="未登录时业务操作显示为 no_permission，不能执行 Review、Ops 或审计查询。" />
        </section>
      </div>
    );
  }

  if (meQuery.isLoading || !meQuery.data) {
    return (
      <div className="s1-console">
        <StateBlock state="loading" title="正在读取当前用户" detail="从 /api/v1/me 获取权限和角色。" />
      </div>
    );
  }

  const user = meQuery.data.data;
  const navigationItems = (navigationQuery.data?.data.items ?? []).filter((item) => item.visible);
  const enabledButtonCount = (navigationQuery.data?.data.button_states ?? []).filter((state) => state.enabled).length;
  return (
    <div className="s1-console" data-testid={`s1-${mode}-console`}>
      <section className="s1-auth-strip">
        <div>
          <span className="s1-kicker">Tenant {user.tenant_id}</span>
          <h2>{user.display_name}</h2>
          <p>{user.username} · {user.roles.map((role) => role.name).join(", ") || "no role"}</p>
        </div>
        <div className="s1-permissions">
          {user.permissions.slice(0, 8).map((permission) => (
            <span key={permission}>{permission}</span>
          ))}
        </div>
        <button className="admin-button secondary" type="button" disabled={logout.isPending} onClick={() => logout.mutate()}>
          <LogOut size={16} />
          退出
        </button>
      </section>
      {navigationQuery.isLoading ? <StateLine tone="loading" text="Loading navigation from /api/v1/me/navigation." /> : null}
      {navigationQuery.isError ? <StateLine tone="error" text={(navigationQuery.error as Error).message} /> : null}
      {navigationQuery.data ? (
        <StateLine
          tone="empty"
          text={`Navigation: ${navigationItems.map((item) => item.label).join(", ") || "no visible surfaces"} · ${enabledButtonCount} enabled actions.`}
        />
      ) : null}

      {mode === "foundation" ? <FoundationBody /> : null}
      {mode === "reviews" ? <ReviewBody /> : null}
      {mode === "ops" ? <OpsBody /> : null}
    </div>
  );
}

function FoundationBody() {
  const queryClient = useQueryClient();
  const [roleName, setRoleName] = useState("s1_reviewer");
  const [permissionText, setPermissionText] = useState("audit:read,review:write,ops:read");
  const [newUsername, setNewUsername] = useState("s1.operator");
  const [newDisplayName, setNewDisplayName] = useState("S1 Operator");
  const [newPassword, setNewPassword] = useState("StrongPass123!");
  const [selectedRoleId, setSelectedRoleId] = useState("");

  const users = useQuery({ queryKey: ["s1-users"], queryFn: api.listUsers });
  const roles = useQuery({ queryKey: ["s1-roles"], queryFn: api.listRoles });
  const audit = useQuery({ queryKey: ["s1-audit"], queryFn: api.listS1AuditLogs });

  useEffect(() => {
    if (!selectedRoleId && roles.data?.data.length) {
      setSelectedRoleId(roles.data.data[0].role_id);
    }
  }, [roles.data, selectedRoleId]);

  const createRole = useMutation({
    mutationFn: () => api.createRole(roleName, permissionText.split(",").map((item) => item.trim()).filter(Boolean)),
    onSuccess: async (result) => {
      setSelectedRoleId(result.data.role_id);
      await queryClient.invalidateQueries({ queryKey: ["s1-roles"] });
      await queryClient.invalidateQueries({ queryKey: ["s1-audit"] });
    }
  });

  const createUser = useMutation({
    mutationFn: () => api.createUser(newUsername, newDisplayName, newPassword, selectedRoleId ? [selectedRoleId] : []),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["s1-users"] });
      await queryClient.invalidateQueries({ queryKey: ["s1-audit"] });
    }
  });

  return (
    <div className="s1-grid">
      <section className="s1-card">
        <CardTitle icon={Users} title="用户与角色" meta={users.data ? `${users.data.data.length} users` : "loading"} />
        {users.isLoading ? <StateLine tone="loading" text="加载用户列表" /> : null}
        {users.isError ? <StateLine tone="error" text={(users.error as Error).message} /> : null}
        <div className="s1-list">
          {(users.data?.data ?? []).map((user) => (
            <div className="s1-row" key={user.user_id}>
              <b>{user.display_name}</b>
              <span>{user.username}</span>
              <small>{user.status}</small>
            </div>
          ))}
          {users.data?.data.length === 0 ? <StateLine tone="empty" text="empty: 尚无用户记录" /> : null}
        </div>
      </section>

      <section className="s1-card">
        <CardTitle icon={ShieldCheck} title="创建角色和用户" meta="backend mutation" />
        <div className="s1-form-grid">
          <label>角色名<input value={roleName} onChange={(event) => setRoleName(event.target.value)} /></label>
          <label>权限点<input value={permissionText} onChange={(event) => setPermissionText(event.target.value)} /></label>
          <button className="admin-button secondary" type="button" disabled={createRole.isPending} onClick={() => createRole.mutate()}>创建角色</button>
          <label>用户<input value={newUsername} onChange={(event) => setNewUsername(event.target.value)} /></label>
          <label>显示名<input value={newDisplayName} onChange={(event) => setNewDisplayName(event.target.value)} /></label>
          <label>密码<input value={newPassword} onChange={(event) => setNewPassword(event.target.value)} type="password" /></label>
          <label>
            角色
            <select value={selectedRoleId} onChange={(event) => setSelectedRoleId(event.target.value)}>
              {(roles.data?.data ?? []).map((role) => (
                <option key={role.role_id} value={role.role_id}>{role.name}</option>
              ))}
            </select>
          </label>
          <button className="admin-button primary" type="button" disabled={createUser.isPending || !selectedRoleId} onClick={() => createUser.mutate()}>创建用户</button>
        </div>
        {createRole.isError ? <StateLine tone="error" text={(createRole.error as Error).message} /> : null}
        {createUser.isError ? <StateLine tone="error" text={(createUser.error as Error).message} /> : null}
      </section>

      <section className="s1-card s1-wide">
        <CardTitle icon={FileCheck2} title="S1 审计日志" meta={audit.data?.trace_id ?? "trace pending"} />
        {audit.isLoading ? <StateLine tone="loading" text="加载审计日志" /> : null}
        {audit.isError ? <StateLine tone="error" text={(audit.error as Error).message} /> : null}
        <div className="s1-table">
          {(audit.data?.data ?? []).slice(0, 12).map((entry) => (
            <div className="s1-table-row" key={entry.audit_id}>
              <span>{entry.action}</span>
              <span>{entry.object_type}</span>
              <span>{entry.actor}</span>
              <span>{entry.trace_id ?? "no-trace"}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function ReviewBody() {
  const queryClient = useQueryClient();
  const [lastGate, setLastGate] = useState<string>("");
  const templates = useQuery({ queryKey: ["s1-review-templates"], queryFn: () => api.listReviewTemplates("api") });
  const reviews = useQuery({ queryKey: ["s1-reviews"], queryFn: api.listReviews });

  const createReview = useMutation({
    mutationFn: () => api.createReview("api", "packages/contracts/openapi/v1.0.yaml", "1.0.0", "TPL-API-V1"),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["s1-reviews"] })
  });
  const markPass = useMutation({
    mutationFn: (reviewId: string) => api.updateReview(reviewId, "pass", ["review completed from browser"], []),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["s1-reviews"] })
  });
  const markFail = useMutation({
    mutationFn: (reviewId: string) => api.updateReview(reviewId, "fail", ["trace propagation needs verification"], ["missing trace propagation"]),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["s1-reviews"] })
  });
  const gateCheck = useMutation({
    mutationFn: (reviewId: string) => api.gateCheck(reviewId),
    onSuccess: (result) => setLastGate(`${result.data.passed ? "passed" : "blocked"} · ${result.data.blockers.join(", ") || "no blockers"} · ${result.trace_id}`)
  });
  const waive = useMutation({
    mutationFn: (reviewId: string) => api.waiveReview(reviewId, "Browser waiver with persisted audit trail.", "S1 bootstrap validation only."),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["s1-reviews"] })
  });

  const reviewRows = reviews.data?.data ?? [];
  return (
    <div className="s1-grid">
      <section className="s1-card">
        <CardTitle icon={FileCheck2} title="Review 模板" meta={templates.data?.trace_id ?? "trace pending"} />
        {templates.isLoading ? <StateLine tone="loading" text="加载模板" /> : null}
        {templates.isError ? <StateLine tone="error" text={(templates.error as Error).message} /> : null}
        <div className="s1-list">
          {(templates.data?.data ?? []).map((template) => (
            <div className="s1-row" key={template.id}>
              <b>{template.id}</b>
              <span>{template.name}</span>
              <small>{template.checklist.length} checks</small>
            </div>
          ))}
        </div>
        <button className="admin-button primary" type="button" disabled={createReview.isPending} onClick={() => createReview.mutate()}>
          <Play size={16} />
          创建 API Review
        </button>
        {createReview.isError ? <StateLine tone="error" text={(createReview.error as Error).message} /> : null}
      </section>

      <section className="s1-card s1-wide">
        <CardTitle icon={ShieldCheck} title="Review Gate" meta={lastGate || "not checked"} />
        {reviews.isLoading ? <StateLine tone="loading" text="加载 Review 列表" /> : null}
        {reviews.isError ? <StateLine tone="error" text={(reviews.error as Error).message} /> : null}
        {reviewRows.length === 0 ? <StateLine tone="empty" text="empty: 尚无 Review，先创建一条 API Review。" /> : null}
        <div className="s1-review-list">
          {reviewRows.map((review) => (
            <ReviewRow
              key={review.review_id}
              review={review}
              onPass={() => markPass.mutate(review.review_id)}
              onFail={() => markFail.mutate(review.review_id)}
              onGate={() => gateCheck.mutate(review.review_id)}
              onWaive={() => waive.mutate(review.review_id)}
            />
          ))}
        </div>
      </section>
    </div>
  );
}

function OpsBody() {
  const queryClient = useQueryClient();
  const apiHealth = useQuery({ queryKey: ["s1-ops", "api"], queryFn: api.opsApiHealth });
  const dbHealth = useQuery({ queryKey: ["s1-ops", "db"], queryFn: api.opsDbHealth });
  const workers = useQuery({ queryKey: ["s1-ops", "workers"], queryFn: api.opsWorkers });
  const workflowRuns = useQuery({ queryKey: ["s1-ops", "workflow-runs"], queryFn: api.opsWorkflowRuns });
  const errorQueue = useQuery({ queryKey: ["s1-ops", "error-queue"], queryFn: api.opsErrorQueue });
  const retryQueue = useQuery({ queryKey: ["s1-ops", "retry-queue"], queryFn: api.opsRetryQueue });
  const metrics = useQuery({ queryKey: ["s1-ops", "metrics"], queryFn: api.opsMetrics });

  const degraded = [apiHealth, dbHealth, workers, workflowRuns, errorQueue, retryQueue, metrics].some((query) => query.isError);
  return (
    <div className="s1-grid">
      <section className="s1-card s1-wide">
        <CardTitle icon={Database} title="Ops Health" meta={degraded ? "degraded" : "ready"} />
        <button className="admin-button secondary" type="button" onClick={() => queryClient.invalidateQueries({ queryKey: ["s1-ops"] })}>
          <RefreshCw size={16} />
          刷新健康状态
        </button>
        <div className="s1-ops-grid">
          <OpsTile title="API" query={apiHealth} />
          <OpsTile title="DB" query={dbHealth} />
          <OpsTile title="Workers" query={workers} />
          <OpsTile title="Workflow Runs" query={workflowRuns} />
          <OpsTile title="Error Queue" query={errorQueue} />
          <OpsTile title="Retry Queue" query={retryQueue} />
          <OpsTile title="Metrics" query={metrics} />
        </div>
      </section>
    </div>
  );
}

function ReviewRow({
  review,
  onPass,
  onFail,
  onGate,
  onWaive
}: {
  review: ReviewRecord;
  onPass: () => void;
  onFail: () => void;
  onGate: () => void;
  onWaive: () => void;
}) {
  return (
    <article className="s1-review-row">
      <div>
        <b>{review.object_type} · {review.object_version}</b>
        <span>{review.object_id}</span>
      </div>
      <StatusBadge status={review.status} />
      <div className="s1-row-actions">
        <button type="button" onClick={onGate}>Gate</button>
        <button type="button" onClick={onPass}>Pass</button>
        <button type="button" onClick={onFail}>Fail</button>
        <button type="button" onClick={onWaive}>Waive</button>
      </div>
    </article>
  );
}

function OpsTile({ title, query }: { title: string; query: { isLoading: boolean; isError: boolean; error: unknown; data?: { data: unknown; trace_id: string } } }) {
  const count = useMemo(() => {
    if (!query.data) return "";
    return Array.isArray(query.data.data) ? `${query.data.data.length} records` : "recorded";
  }, [query.data]);
  return (
    <div className={query.isError ? "s1-ops-tile error" : "s1-ops-tile"}>
      <b>{title}</b>
      {query.isLoading ? <span>loading</span> : null}
      {query.isError ? <span>{(query.error as Error).message}</span> : null}
      {query.data ? <span>{count} · {query.data.trace_id}</span> : null}
    </div>
  );
}

function CardTitle({ icon: Icon, title, meta }: { icon: LucideIcon; title: string; meta: string }) {
  return (
    <header className="s1-card-title">
      <span><Icon size={16} />{title}</span>
      <small>{meta}</small>
    </header>
  );
}

function StatusBadge({ status }: { status: string }) {
  const passed = status === "pass" || status === "waived";
  return <span className={passed ? "s1-status ok" : status === "fail" ? "s1-status error" : "s1-status"}>{status}</span>;
}

function StateBlock({ state, title, detail }: { state: "loading" | "empty" | "error"; title: string; detail: string }) {
  return (
    <section className={`s1-state ${state}`}>
      {state === "error" ? <AlertTriangle size={18} /> : <CheckCircle2 size={18} />}
      <b>{title}</b>
      <span>{detail}</span>
    </section>
  );
}

function StateLine({ tone, text }: { tone: "loading" | "empty" | "error"; text: string }) {
  return <p className={`s1-line ${tone}`}>{text}</p>;
}
