const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class ApiClient {
  private token: string | null = null;

  constructor() {
    if (typeof window !== "undefined") {
      this.token = localStorage.getItem("token");
    }
  }

  setToken(token: string) {
    this.token = token;
    if (typeof window !== "undefined") {
      localStorage.setItem("token", token);
    }
  }

  clearToken() {
    this.token = null;
    if (typeof window !== "undefined") {
      localStorage.removeItem("token");
    }
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    };

    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }

    const res = await fetch(`${API_URL}${path}`, { ...options, headers });

    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `API error: ${res.status}`);
    }

    return res.json();
  }

  // Auth
  async login(email: string, password: string) {
    const data = await this.request<{ token: string; user: any }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    this.setToken(data.token);
    return data;
  }

  async register(email: string, password: string, name: string, company?: string) {
    const data = await this.request<{ token: string; user: any }>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, name, company }),
    });
    this.setToken(data.token);
    return data;
  }

  // Projects
  async listProjects() {
    return this.request<any[]>("/api/projects/");
  }

  async createProject(name: string, description?: string) {
    return this.request<any>("/api/projects/", {
      method: "POST",
      body: JSON.stringify({ name, description }),
    });
  }

  // Parts
  async getPart(partId: string) {
    return this.request<any>(`/api/parts/${partId}`);
  }

  async listParts(projectId: string) {
    return this.request<any[]>(`/api/parts/?project_id=${projectId}`);
  }

  // Analysis
  async startDfmAnalysis(partId: string, pullDirection?: number[], materialId?: string) {
    return this.request<any>("/api/analysis/dfm", {
      method: "POST",
      body: JSON.stringify({
        part_id: partId,
        pull_direction: pullDirection || [0, 0, 1],
        material_id: materialId || "default",
      }),
    });
  }

  async getDfmResult(partId: string) {
    return this.request<any>(`/api/analysis/dfm/${partId}/latest`);
  }

  // Jobs
  async getJobStatus(jobId: string) {
    return this.request<any>(`/api/jobs/${jobId}`);
  }
}

export const api = new ApiClient();
