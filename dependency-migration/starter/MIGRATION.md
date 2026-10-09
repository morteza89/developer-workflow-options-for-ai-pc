# Shared Migration Notes

The unchanged v1 service is now running with Pydantic 2.12.3 and pydantic-settings 2.11.0. Startup fails on legacy root_validator usage and the moved BaseSettings import. Every model receives these same notes.

Official guide: https://docs.pydantic.dev/latest/migration/
Official utility: https://github.com/pydantic/bump-pydantic

- BaseSettings moved to pydantic_settings. SettingsConfigDict supports env_prefix.
- Replace class Config with model_config = ConfigDict(...). allow_population_by_field_name becomes populate_by_name; orm_mode becomes from_attributes.
- validator becomes field_validator. pre=True becomes mode="before". Cross-field model_validator(mode="after") receives a model instance and must return it.
- Optional[T] without a default is required in v2. Explicit defaults are needed when omission should be accepted.
- Numeric-to-string coercion is not enabled by default in v2. Preserve the published integer merchant-code behavior explicitly.
- dict becomes model_dump; from_orm becomes model_validate with from_attributes enabled. Keep by_alias and exclude_unset semantics.
- The codemod handles mechanical changes, not all validators, call sites, or semantic behavior. Use `bump-pydantic --log-file /tmp/bump-pydantic.log app` to keep its diagnostic log outside the submitted workspace. Run tests after using it.