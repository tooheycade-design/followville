import { FileCompanyRepository } from "./file-repository";
import { SupabaseCompanyRepository } from "./supabase-repository";
import type { CompanyRepository } from "./types";

export * from "./types";
export { FileCompanyRepository, defaultStatePath } from "./file-repository";
export { SupabaseCompanyRepository } from "./supabase-repository";

let cached: CompanyRepository | null = null;

/**
 * Chooses the backend from the environment. Supabase is used when both
 * `SUPABASE_URL` and `SUPABASE_SECRET_KEY` are present; otherwise the local
 * JSON store keeps single-machine development working with no credentials.
 * The dashboard shows which backend is active so the distinction is never
 * silent.
 */
export function companyRepository(): CompanyRepository {
  if (cached === null) {
    cached = SupabaseCompanyRepository.fromEnvironment() ?? new FileCompanyRepository();
  }
  return cached;
}

/** Test seam: replaces the cached repository. */
export function setCompanyRepository(repository: CompanyRepository | null): void {
  cached = repository;
}
