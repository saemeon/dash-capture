# Tests for frame_python.R — Python detection and subprocess call

test_that("find_python returns a valid path", {
  skip_on_ci()
  python <- find_python()
  expect_true(file.exists(python))
})

test_that("find_python with explicit path returns it", {
  skip_on_ci()
  python <- find_python()
  python2 <- find_python(python)
  expect_equal(python2, python)
})

test_that("find_python errors on invalid path", {
  expect_error(
    find_python("/nonexistent/python99"),
    "not found"
  )
})

test_that("apply_frame returns raw bytes", {
  skip_on_ci()

  python <- find_python()

  tmp_in <- tempfile(fileext = ".png")
  on.exit(unlink(tmp_in))

  system2(python, c("-c", shQuote(paste0(
    "import matplotlib; matplotlib.use('agg'); ",
    "import matplotlib.pyplot as plt; ",
    "fig, ax = plt.subplots(figsize=(2,1), dpi=72); ",
    "ax.plot([0,1],[0,1]); ",
    "fig.savefig('", tmp_in, "', format='png'); ",
    "plt.close(fig)"
  ))))

  expect_true(file.exists(tmp_in))
  png_bytes <- readBin(tmp_in, "raw", file.info(tmp_in)$size)

  result <- apply_frame(
    png_bytes,
    title = "Test Title",
    subtitle = "Test Subtitle",
    python = python
  )

  expect_type(result, "raw")
  expect_true(length(result) > 100)
  expect_equal(result[1:4], charToRaw("\x89PNG"))
})

test_that("apply_frame with all text params", {
  skip_on_ci()

  python <- find_python()

  tmp_in <- tempfile(fileext = ".png")
  on.exit(unlink(tmp_in))

  system2(python, c("-c", shQuote(paste0(
    "import matplotlib; matplotlib.use('agg'); ",
    "import matplotlib.pyplot as plt; ",
    "fig = plt.figure(figsize=(2,1), dpi=72); ",
    "fig.savefig('", tmp_in, "', format='png'); ",
    "plt.close(fig)"
  ))))

  png_bytes <- readBin(tmp_in, "raw", file.info(tmp_in)$size)

  result <- apply_frame(
    png_bytes,
    title = "Revenue Q4",
    subtitle = "By Region",
    footnotes = "Preliminary",
    sources = "Source: ERP",
    python = python
  )

  expect_type(result, "raw")
  expect_equal(result[1:4], charToRaw("\x89PNG"))
})
