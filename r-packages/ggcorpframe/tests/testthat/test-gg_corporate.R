# Tests for gg_corporate.R — ggsave_corporate and ggsave_corporate_bytes

test_that("ggsave_corporate_bytes returns valid PNG", {
  skip_on_ci()

  p <- ggplot2::ggplot(mtcars, ggplot2::aes(wt, mpg)) +
    ggplot2::geom_point()

  result <- ggsave_corporate_bytes(p,
    title = "Test Title",
    width = 4, height = 3, dpi = 72
  )

  expect_type(result, "raw")
  expect_true(length(result) > 100)
  expect_equal(result[1:4], charToRaw("\x89PNG"))
})

test_that("ggsave_corporate_bytes with all text params", {
  skip_on_ci()

  p <- ggplot2::ggplot(mtcars, ggplot2::aes(wt, mpg)) +
    ggplot2::geom_point()

  result <- ggsave_corporate_bytes(p,
    title = "Weight vs MPG",
    subtitle = "mtcars dataset",
    footnotes = "N = 32 observations",
    sources = "Source: R datasets",
    width = 4, height = 3, dpi = 72
  )

  expect_type(result, "raw")
  expect_equal(result[1:4], charToRaw("\x89PNG"))
})

test_that("ggsave_corporate saves to file", {
  skip_on_ci()

  p <- ggplot2::ggplot(mtcars, ggplot2::aes(wt, mpg)) +
    ggplot2::geom_point()

  tmp <- tempfile(fileext = ".png")
  on.exit(unlink(tmp))

  result <- ggsave_corporate(p, tmp,
    title = "Test Save",
    width = 4, height = 3, dpi = 72
  )

  expect_equal(result, tmp)
  expect_true(file.exists(tmp))
  expect_true(file.info(tmp)$size > 100)

  # Verify it's a valid PNG
  bytes <- readBin(tmp, "raw", 4)
  expect_equal(bytes, charToRaw("\x89PNG"))
})

test_that("ggsave_corporate returns filename invisibly", {
  skip_on_ci()

  p <- ggplot2::ggplot(mtcars, ggplot2::aes(wt, mpg)) +
    ggplot2::geom_point()

  tmp <- tempfile(fileext = ".png")
  on.exit(unlink(tmp))

  result <- ggsave_corporate(p, tmp, title = "T", width = 4, height = 3, dpi = 72)
  expect_equal(result, tmp)
})
