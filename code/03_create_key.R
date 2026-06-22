## ------------------------------------- ##
## Find missing data and rename files
## ------------------------------------- ##


suppressWarnings(suppressMessages(library(jsonlite)))
suppressWarnings(suppressMessages(library(dplyr)))
suppressWarnings(suppressMessages(library(stringr)))

out_dir <- file.path("podcast_analysis", "transcript_key")
if (!dir.exists(out_dir)) dir.create(out_dir, recursive = TRUE)
create_key <- list()
json_files <- list.files("podcast_analysis/json_data")
json_files <- json_files[json_files != "episode_names.json"]
for (i in seq_along(json_files)) {
  
  json_path <- file.path("podcast_analysis", "json_data", json_files[i])
  json_file_temp <- read_json(json_path)
  
  json_name <- sub("\\.json$", "", json_files[i])
  
  episode_airdate <- unlist(json_file_temp$episode_airdate)
  n <- length(episode_airdate)
  episode_number <- seq_len(n)
  
  date_id <- format(as.POSIXct(episode_airdate, tz = "UTC"), "%Y%m%d%H%M%S")
  new_title <- paste0(json_name, "_", date_id, "_", episode_number, ".txt")
  
  data_key <- data.frame(
    episode_airdate = episode_airdate,
    url = unlist(json_file_temp$episode_audio_url),
    episode_title = unlist(json_file_temp$episode_title),
    date_id = date_id,
    new_title = new_title,
    stringsAsFactors = FALSE
  ) %>% arrange(
    episode_airdate, new_title, url
  ) %>% mutate(
    episode_number = episode_number
  )
  
  transcript_dir <- file.path("podcast_analysis", "transcripts", json_name)
  transcript_check <- list.files(transcript_dir, pattern = "\\.txt$", full.names = FALSE)
  
  # parse episode_number from existing filenames
  existing_num <- as.integer(str_match(transcript_check,
                                       paste0("^", fixed(json_name), "_([0-9]+)_"))[, 2])
  
  rename_plan <- data.frame(
    old_file = transcript_check,
    episode_number = existing_num,
    stringsAsFactors = FALSE
  ) %>%
    filter(!is.na(episode_number)) %>%
    left_join(data_key, by = "episode_number") %>%
    filter(!is.na(new_title))
  
  # full paths
  rename_plan$old_path <- file.path(transcript_dir, rename_plan$old_file)
  rename_plan$new_path <- file.path(out_dir, rename_plan$new_title)
  
  # safety: skip if old missing or new exists
  rename_plan$old_exists <- file.exists(rename_plan$old_path)
  rename_plan$new_exists <- file.exists(rename_plan$new_path)
  
  do_rename <- rename_plan %>% filter(old_exists, !new_exists)
  
  for (k in seq_len(nrow(do_rename))) {
    
    from <- do_rename$old_path[k]
    to   <- do_rename$new_path[k]
    
    # --- preflight checks ---
    if (!file.exists(from)) {
      message("FAILED (missing source): ", from)
      next
    }
    
    # make sure destination directory exists
    to_dir <- dirname(to)
    if (!dir.exists(to_dir)) dir.create(to_dir, recursive = TRUE)
    
    # --- do the copy ---
    ok <- file.copy(from = from, to = to, overwrite = TRUE)
    
    if (!ok) {
      message("FAILED (copy returned FALSE): ", from, " -> ", to)
      
      # extra diagnostics (helpful on Windows / Dropbox)
      message("  nchar(from) = ", nchar(from), " | nchar(to) = ", nchar(to))
      message("  from_readable = ", file.access(from, 4) == 0, " | to_writable_dir = ", file.access(to_dir, 2) == 0)
      
      # if file may be locked, try forcing a remove then copy again
      if (file.exists(to)) file.remove(to)
      ok2 <- file.copy(from = from, to = to, overwrite = TRUE)
      if (!ok2) message("  FAILED again after retry: ", from, " -> ", to)
    }
  }
  
  cat(json_name, ": renamed ", nrow(do_rename), " files; skipped existing targets ",
      sum(rename_plan$new_exists), "\n")
  
  create_key[[i]] <- data_key
}


key_all <- bind_rows(create_key)

# optional: keep show name explicitly
key_all <- key_all %>%
  mutate(json_name = sub("_[0-9]{14}.*$", "", new_title)) %>%
  distinct(url, .keep_all = T)  %>% 
  mutate(date_id = paste0("'", date_id))


out_dir <- file.path("podcast_analysis", "transcript_key")
out_files <- list.files(out_dir, pattern = "\\.txt$", full.names = FALSE)

missing_in_key <- key_all %>%
  filter(!(new_title %in% out_files)) %>%
  distinct(url, .keep_all = T)
write.csv(missing_in_key, file = "podcast_analysis/missing_files.csv")
write.csv(key_all, file = "podcast_analysis/file_key.csv")
cat("Expected transcripts:", nrow(key_all), "\n")
cat("Found in transcript_key:", length(out_files), "\n")
cat("Missing in transcript_key:", nrow(missing_in_key), "\n")
