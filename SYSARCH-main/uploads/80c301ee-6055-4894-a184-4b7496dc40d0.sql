-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Generation Time: May 05, 2025 at 09:05 PM
-- Server version: 10.4.32-MariaDB
-- PHP Version: 8.2.12

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `students`
--

-- --------------------------------------------------------

--
-- Table structure for table `admins`
--

CREATE TABLE `admins` (
  `id` int(11) NOT NULL,
  `username` varchar(50) NOT NULL,
  `password` varchar(255) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `admins`
--

INSERT INTO `admins` (`id`, `username`, `password`, `created_at`) VALUES
(1, 'admin', 'pbkdf2:sha256:260000$fXQWPdiIBinUbHOp$9f028e862e4552655cb2f7756b4cf0e2ab5978a4cb774e4465c9566e01266e70', '2025-05-01 11:43:21');

-- --------------------------------------------------------

--
-- Table structure for table `announcements`
--

CREATE TABLE `announcements` (
  `id` int(11) NOT NULL,
  `title` varchar(100) NOT NULL,
  `content` text NOT NULL,
  `is_active` tinyint(1) DEFAULT 1,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `announcements`
--

INSERT INTO `announcements` (`id`, `title`, `content`, `is_active`, `created_at`) VALUES
(1, 'WELCOME!!!!', 'WELCOME STUDENTS!!', 1, '2025-05-04 07:27:01');

-- --------------------------------------------------------

--
-- Table structure for table `feedback`
--

CREATE TABLE `feedback` (
  `id` int(11) NOT NULL,
  `session_id` int(11) NOT NULL,
  `student_id` int(11) NOT NULL,
  `rating` int(11) NOT NULL,
  `comments` text DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `feedback`
--

INSERT INTO `feedback` (`id`, `session_id`, `student_id`, `rating`, `comments`, `created_at`) VALUES
(1, 1, 1, 5, 'asdsad', '2025-05-04 07:31:37');

-- --------------------------------------------------------

--
-- Table structure for table `lab_resources`
--

CREATE TABLE `lab_resources` (
  `id` int(11) NOT NULL,
  `title` varchar(255) NOT NULL,
  `description` text DEFAULT NULL,
  `file_path` varchar(255) DEFAULT NULL,
  `resource_type` enum('ppt','discussion','document','other') NOT NULL,
  `lab_room` varchar(50) NOT NULL,
  `is_enabled` tinyint(1) DEFAULT 1,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `lab_resources`
--

INSERT INTO `lab_resources` (`id`, `title`, `description`, `file_path`, `resource_type`, `lab_room`, `is_enabled`, `created_at`, `updated_at`) VALUES
(2, 'SASJDSAHDJ', 'ASDJSDA', 'https://www.reddit.com/?rdt=51203', '', 'All', 1, '2025-05-05 12:09:05', '2025-05-05 12:09:05'),
(4, 'jadhkajhdjahwjdh', 'asjhdjshdja', 'uploads/20250506003047_COC_CHA.docx', '', 'All', 1, '2025-05-05 16:30:47', '2025-05-05 16:30:47'),
(5, 'TUTURIAL', 'SADASDWA', 'uploads/20250506025028_COC_CHA.pdf', '', 'All', 1, '2025-05-05 18:50:28', '2025-05-05 18:50:28');

-- --------------------------------------------------------

--
-- Table structure for table `lab_schedules`
--

CREATE TABLE `lab_schedules` (
  `id` int(11) NOT NULL,
  `lab_room` varchar(50) NOT NULL,
  `day_of_week` varchar(20) NOT NULL,
  `start_time` time NOT NULL,
  `end_time` time NOT NULL,
  `instructor` varchar(100) DEFAULT NULL,
  `subject` varchar(100) DEFAULT NULL,
  `section` varchar(50) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `lab_schedules`
--

INSERT INTO `lab_schedules` (`id`, `lab_room`, `day_of_week`, `start_time`, `end_time`, `instructor`, `subject`, `section`, `created_at`) VALUES
(7, 'Lab 7', 'Monday', '12:00:00', '13:00:00', 'Engr. Jeff P. Salimbangon', 'SYSARCH', '', '2025-05-04 09:21:52'),
(8, 'Lab 1', 'Tuesday', '13:30:00', '15:00:00', 'Dennis Durano', 'SYSAD', '', '2025-05-04 09:22:12'),
(9, 'Lab 4', 'Tuesday', '08:00:00', '10:30:00', 'Leo Bermudes', 'ELNET', '', '2025-05-04 09:22:37'),
(10, 'Lab 2', 'Monday', '10:30:00', '11:00:00', 'Engr. Jeff P.Salimbangon', 'SYSARCH', '', '2025-05-05 16:49:50');

-- --------------------------------------------------------

--
-- Table structure for table `pc_status`
--

CREATE TABLE `pc_status` (
  `id` int(11) NOT NULL,
  `lab_room` varchar(50) NOT NULL,
  `pc_number` int(11) NOT NULL,
  `status` varchar(20) DEFAULT 'vacant',
  `last_updated` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `pc_status`
--

INSERT INTO `pc_status` (`id`, `lab_room`, `pc_number`, `status`, `last_updated`) VALUES
(1, 'Lab 1', 1, 'occupied', '2025-05-05 18:43:56'),
(2, 'Lab 1', 2, 'maintenance', '2025-05-05 16:53:54'),
(3, 'Lab 1', 3, 'maintenance', '2025-05-05 16:53:54'),
(4, 'Lab 1', 4, 'maintenance', '2025-05-05 16:53:54'),
(5, 'Lab 1', 5, 'maintenance', '2025-05-05 16:53:54'),
(6, 'Lab 1', 6, 'maintenance', '2025-05-05 16:53:54'),
(7, 'Lab 1', 7, 'maintenance', '2025-05-05 16:53:54'),
(8, 'Lab 1', 8, 'maintenance', '2025-05-05 16:53:54'),
(9, 'Lab 1', 9, 'maintenance', '2025-05-05 16:53:54'),
(10, 'Lab 1', 10, 'maintenance', '2025-05-05 16:53:54'),
(11, 'Lab 1', 11, 'maintenance', '2025-05-05 16:53:54'),
(12, 'Lab 1', 12, 'maintenance', '2025-05-05 16:53:54'),
(13, 'Lab 1', 13, 'maintenance', '2025-05-05 16:53:54'),
(14, 'Lab 1', 14, 'maintenance', '2025-05-05 16:53:54'),
(15, 'Lab 1', 15, 'maintenance', '2025-05-05 16:53:54'),
(16, 'Lab 1', 16, 'maintenance', '2025-05-05 16:53:54'),
(17, 'Lab 1', 17, 'maintenance', '2025-05-05 16:53:54'),
(18, 'Lab 1', 18, 'maintenance', '2025-05-05 16:53:54'),
(19, 'Lab 1', 19, 'maintenance', '2025-05-05 16:53:54'),
(20, 'Lab 1', 20, 'maintenance', '2025-05-05 16:53:54'),
(21, 'Lab 1', 21, 'maintenance', '2025-05-05 16:53:54'),
(22, 'Lab 1', 22, 'maintenance', '2025-05-05 16:53:54'),
(23, 'Lab 1', 23, 'maintenance', '2025-05-05 16:53:54'),
(24, 'Lab 1', 24, 'maintenance', '2025-05-05 16:53:54'),
(25, 'Lab 1', 25, 'maintenance', '2025-05-05 16:53:54'),
(26, 'Lab 1', 26, 'maintenance', '2025-05-05 16:53:54'),
(27, 'Lab 1', 27, 'maintenance', '2025-05-05 16:53:54'),
(28, 'Lab 1', 28, 'maintenance', '2025-05-05 16:53:54'),
(29, 'Lab 1', 29, 'maintenance', '2025-05-05 16:53:54'),
(30, 'Lab 1', 30, 'maintenance', '2025-05-05 16:53:54'),
(31, 'Lab 1', 31, 'maintenance', '2025-05-05 16:53:54'),
(32, 'Lab 1', 32, 'maintenance', '2025-05-05 16:53:54'),
(33, 'Lab 1', 33, 'maintenance', '2025-05-05 16:53:54'),
(34, 'Lab 1', 34, 'maintenance', '2025-05-05 16:53:54'),
(35, 'Lab 1', 35, 'maintenance', '2025-05-05 16:53:54'),
(36, 'Lab 1', 36, 'maintenance', '2025-05-05 16:53:54'),
(37, 'Lab 1', 37, 'maintenance', '2025-05-05 16:53:54'),
(38, 'Lab 1', 38, 'maintenance', '2025-05-05 16:53:54'),
(39, 'Lab 1', 39, 'maintenance', '2025-05-05 16:53:54'),
(40, 'Lab 1', 40, 'maintenance', '2025-05-05 16:53:54'),
(41, 'Lab 1', 41, 'maintenance', '2025-05-05 16:53:54'),
(42, 'Lab 1', 42, 'maintenance', '2025-05-05 16:53:54'),
(43, 'Lab 1', 43, 'maintenance', '2025-05-05 16:53:54'),
(44, 'Lab 1', 44, 'maintenance', '2025-05-05 16:53:54'),
(45, 'Lab 1', 45, 'maintenance', '2025-05-05 16:53:54'),
(46, 'Lab 1', 46, 'maintenance', '2025-05-05 16:53:54'),
(47, 'Lab 1', 47, 'maintenance', '2025-05-05 16:53:54'),
(48, 'Lab 1', 48, 'maintenance', '2025-05-05 16:53:54'),
(49, 'Lab 1', 49, 'maintenance', '2025-05-05 16:53:54'),
(50, 'Lab 1', 50, 'maintenance', '2025-05-05 16:53:54'),
(51, 'Lab 2', 1, 'occupied', '2025-05-05 17:06:42'),
(52, 'Lab 2', 2, 'occupied', '2025-05-05 17:06:42'),
(53, 'Lab 2', 3, 'occupied', '2025-05-05 17:06:42'),
(54, 'Lab 2', 4, 'occupied', '2025-05-05 17:06:42'),
(55, 'Lab 2', 5, 'occupied', '2025-05-05 17:06:42'),
(56, 'Lab 2', 6, 'occupied', '2025-05-05 17:06:42'),
(57, 'Lab 2', 7, 'occupied', '2025-05-05 17:06:42'),
(58, 'Lab 2', 8, 'occupied', '2025-05-05 17:06:42'),
(59, 'Lab 2', 9, 'occupied', '2025-05-05 17:06:42'),
(60, 'Lab 2', 10, 'occupied', '2025-05-05 17:06:42'),
(61, 'Lab 2', 11, 'occupied', '2025-05-05 17:06:42'),
(62, 'Lab 2', 12, 'occupied', '2025-05-05 17:06:42'),
(63, 'Lab 2', 13, 'occupied', '2025-05-05 17:06:42'),
(64, 'Lab 2', 14, 'occupied', '2025-05-05 17:06:42'),
(65, 'Lab 2', 15, 'occupied', '2025-05-05 17:06:42'),
(66, 'Lab 2', 16, 'occupied', '2025-05-05 17:06:42'),
(67, 'Lab 2', 17, 'occupied', '2025-05-05 17:06:42'),
(68, 'Lab 2', 18, 'occupied', '2025-05-05 17:06:42'),
(69, 'Lab 2', 19, 'occupied', '2025-05-05 17:06:42'),
(70, 'Lab 2', 20, 'occupied', '2025-05-05 17:06:42'),
(71, 'Lab 2', 21, 'occupied', '2025-05-05 17:06:42'),
(72, 'Lab 2', 22, 'occupied', '2025-05-05 17:06:42'),
(73, 'Lab 2', 23, 'occupied', '2025-05-05 17:06:42'),
(74, 'Lab 2', 24, 'occupied', '2025-05-05 17:06:42'),
(75, 'Lab 2', 25, 'occupied', '2025-05-05 17:06:42'),
(76, 'Lab 2', 26, 'occupied', '2025-05-05 17:06:42'),
(77, 'Lab 2', 27, 'occupied', '2025-05-05 17:06:42'),
(78, 'Lab 2', 28, 'occupied', '2025-05-05 17:06:42'),
(79, 'Lab 2', 29, 'occupied', '2025-05-05 17:06:42'),
(80, 'Lab 2', 30, 'occupied', '2025-05-05 17:06:42'),
(81, 'Lab 2', 31, 'occupied', '2025-05-05 17:06:42'),
(82, 'Lab 2', 32, 'occupied', '2025-05-05 17:06:42'),
(83, 'Lab 2', 33, 'occupied', '2025-05-05 17:06:42'),
(84, 'Lab 2', 34, 'occupied', '2025-05-05 17:06:42'),
(85, 'Lab 2', 35, 'occupied', '2025-05-05 17:06:42'),
(86, 'Lab 2', 36, 'occupied', '2025-05-05 17:06:42'),
(87, 'Lab 2', 37, 'occupied', '2025-05-05 17:06:42'),
(88, 'Lab 2', 38, 'occupied', '2025-05-05 17:06:42'),
(89, 'Lab 2', 39, 'occupied', '2025-05-05 17:06:42'),
(90, 'Lab 2', 40, 'occupied', '2025-05-05 17:06:42'),
(91, 'Lab 2', 41, 'occupied', '2025-05-05 17:06:42'),
(92, 'Lab 2', 42, 'occupied', '2025-05-05 17:06:42'),
(93, 'Lab 2', 43, 'occupied', '2025-05-05 17:06:42'),
(94, 'Lab 2', 44, 'occupied', '2025-05-05 17:06:42'),
(95, 'Lab 2', 45, 'occupied', '2025-05-05 17:06:42'),
(96, 'Lab 2', 46, 'occupied', '2025-05-05 17:06:42'),
(97, 'Lab 2', 47, 'occupied', '2025-05-05 17:06:42'),
(98, 'Lab 2', 48, 'occupied', '2025-05-05 17:06:42'),
(99, 'Lab 2', 49, 'occupied', '2025-05-05 17:06:42'),
(100, 'Lab 2', 50, 'occupied', '2025-05-05 17:06:42'),
(101, 'Lab 3', 1, 'occupied', '2025-05-05 18:48:12');

-- --------------------------------------------------------

--
-- Table structure for table `points`
--

CREATE TABLE `points` (
  `id` int(11) NOT NULL,
  `student_id` int(11) NOT NULL,
  `points` int(11) DEFAULT 0,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Table structure for table `programming_languages`
--

CREATE TABLE `programming_languages` (
  `id` int(11) NOT NULL,
  `name` varchar(50) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `programming_languages`
--

INSERT INTO `programming_languages` (`id`, `name`, `created_at`) VALUES
(1, 'PHP', '2025-05-01 11:43:21'),
(2, 'Java', '2025-05-01 11:43:21'),
(3, 'Python', '2025-05-01 11:43:21'),
(4, 'JavaScript', '2025-05-01 11:43:21'),
(5, 'C++', '2025-05-01 11:43:21'),
(6, 'C#', '2025-05-01 11:43:21'),
(7, 'Ruby', '2025-05-01 11:43:21'),
(8, 'Swift', '2025-05-01 11:43:21');

-- --------------------------------------------------------

--
-- Table structure for table `reward_logs`
--

CREATE TABLE `reward_logs` (
  `id` int(11) NOT NULL,
  `student_id` int(11) NOT NULL,
  `points` int(11) NOT NULL,
  `reason` text DEFAULT NULL,
  `admin_id` int(11) DEFAULT NULL,
  `timestamp` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Table structure for table `sessions`
--

CREATE TABLE `sessions` (
  `id` int(11) NOT NULL,
  `student_id` int(11) NOT NULL,
  `lab_room` varchar(50) NOT NULL,
  `date_time` datetime NOT NULL,
  `duration` int(11) NOT NULL,
  `programming_language` varchar(50) DEFAULT NULL,
  `purpose` text DEFAULT NULL,
  `status` varchar(20) DEFAULT 'pending',
  `check_in_time` datetime DEFAULT NULL,
  `check_out_time` datetime DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `approval_status` varchar(20) DEFAULT 'pending',
  `pc_number` int(11) DEFAULT NULL,
  `approved_at` timestamp NULL DEFAULT NULL,
  `approved_by` int(11) DEFAULT NULL,
  `rejected_at` timestamp NULL DEFAULT NULL,
  `rejected_by` int(11) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `sessions`
--

INSERT INTO `sessions` (`id`, `student_id`, `lab_room`, `date_time`, `duration`, `programming_language`, `purpose`, `status`, `check_in_time`, `check_out_time`, `created_at`, `approval_status`, `pc_number`, `approved_at`, `approved_by`, `rejected_at`, `rejected_by`) VALUES
(1, 1, 'Lab 1', '2025-05-03 10:00:00', 1, NULL, 'PHP Programming - PC #5', 'completed', NULL, '2025-05-03 01:53:57', '2025-05-02 17:53:48', 'approved', NULL, NULL, NULL, NULL, NULL),
(2, 1, 'Lab 1', '2025-05-03 10:00:00', 1, NULL, 'PHP Programming - PC #1', 'completed', '0000-00-00 00:00:00', '2025-05-04 15:30:54', '2025-05-02 18:06:20', 'approved', NULL, NULL, NULL, NULL, NULL),
(3, 3, 'Lab 1', '2025-05-06 10:00:00', 1, NULL, 'PHP Programming - PC #1', 'completed', '0000-00-00 00:00:00', '2025-05-06 00:08:27', '2025-05-05 11:23:40', 'approved', NULL, NULL, NULL, NULL, NULL),
(4, 1, 'Lab 1', '2025-05-05 12:00:00', 1, NULL, 'PHP Programming - PC #4', 'completed', '2025-05-05 19:50:48', '2025-05-06 00:08:23', '2025-05-05 11:37:42', 'approved', NULL, NULL, NULL, NULL, NULL),
(5, 5, 'Lab 1', '2025-05-06 10:00:00', 1, NULL, 'PHP Programming - PC #12', 'pending', NULL, NULL, '2025-05-05 12:10:16', 'approved', NULL, NULL, NULL, NULL, NULL),
(6, 6, 'Lab 1', '2025-05-06 15:00:00', 1, NULL, 'PHP Programming - PC #10', 'pending', NULL, NULL, '2025-05-05 15:16:30', 'approved', NULL, NULL, NULL, NULL, NULL),
(7, 1, 'Lab 1', '2025-05-06 00:19:47', 24, NULL, 'Lab Maintenance - All PCs', 'completed', '2025-05-06 00:19:47', '2025-05-06 00:19:53', '2025-05-05 16:19:47', 'approved', NULL, NULL, NULL, NULL, NULL),
(8, 1, 'Lab 1', '2025-05-06 00:19:53', 24, NULL, 'Lab Maintenance - All PCs', 'completed', '2025-05-06 00:19:53', '2025-05-06 00:20:07', '2025-05-05 16:19:53', 'approved', NULL, NULL, NULL, NULL, NULL),
(9, 1, 'Lab 1', '2025-05-06 00:20:07', 24, NULL, 'Lab Maintenance - All PCs', 'completed', '2025-05-06 00:20:07', '2025-05-06 00:37:56', '2025-05-05 16:20:07', 'approved', NULL, NULL, NULL, NULL, NULL),
(10, 1, 'Lab 1', '2025-05-06 00:20:12', 24, NULL, 'Maintenance - PC #3', 'completed', '2025-05-06 00:20:12', '2025-05-06 00:37:51', '2025-05-05 16:20:12', 'approved', NULL, NULL, NULL, NULL, NULL),
(11, 1, 'Lab 1', '2025-05-06 00:20:15', 24, NULL, 'Maintenance - PC #1', 'completed', '2025-05-06 00:20:15', '2025-05-06 00:31:20', '2025-05-05 16:20:15', 'approved', NULL, NULL, NULL, NULL, NULL),
(12, 1, 'Lab 1', '2025-05-06 00:31:20', 24, NULL, 'Maintenance - PC #1', 'completed', '2025-05-06 00:31:20', '2025-05-06 00:37:45', '2025-05-05 16:31:20', 'approved', NULL, NULL, NULL, NULL, NULL),
(13, 1, 'Lab 1', '2025-05-06 00:53:54', 24, NULL, 'Lab Maintenance - All PCs', 'completed', '2025-05-06 00:53:54', '2025-05-06 01:41:00', '2025-05-05 16:53:54', 'approved', NULL, NULL, NULL, NULL, NULL),
(14, 1, 'Lab 2', '2025-05-06 01:05:40', 24, NULL, 'Lab Maintenance - All PCs', 'completed', '2025-05-06 01:05:40', '2025-05-06 01:06:40', '2025-05-05 17:05:40', 'approved', NULL, NULL, NULL, NULL, NULL),
(15, 1, 'Lab 2', '2025-05-06 01:06:40', 24, NULL, 'Lab Maintenance - All PCs', 'completed', '2025-05-06 01:06:40', '2025-05-06 01:40:56', '2025-05-05 17:06:40', 'approved', NULL, NULL, NULL, NULL, NULL),
(16, 1, 'Lab 1', '2025-05-06 01:21:50', 24, NULL, 'Maintenance - PC #1', 'completed', '2025-05-06 01:21:50', '2025-05-06 01:40:13', '2025-05-05 17:21:50', 'approved', NULL, NULL, NULL, NULL, NULL),
(17, 5, 'Lab 3', '2025-05-06 10:00:00', 1, NULL, 'PHP Programming - PC #1', 'pending', '2025-05-06 02:12:14', NULL, '2025-05-05 17:41:36', 'approved', 1, NULL, NULL, NULL, NULL),
(18, 1, 'Lab 1', '2025-05-07 10:00:00', 1, NULL, 'Self-Study - PC #1', 'completed', '2025-05-06 02:43:56', '2025-05-06 02:44:47', '2025-05-05 18:43:39', 'approved', 1, NULL, NULL, NULL, NULL),
(19, 1, 'Lab 3', '2025-05-06 10:00:00', 1, NULL, 'Project - PC #1', 'completed', '2025-05-06 02:48:12', '2025-05-06 02:48:26', '2025-05-05 18:47:56', 'approved', 1, NULL, NULL, NULL, NULL);

-- --------------------------------------------------------

--
-- Table structure for table `students`
--

CREATE TABLE `students` (
  `id` int(11) NOT NULL,
  `idno` varchar(20) NOT NULL,
  `lastname` varchar(50) NOT NULL,
  `firstname` varchar(50) NOT NULL,
  `middlename` varchar(50) DEFAULT NULL,
  `course` varchar(100) NOT NULL,
  `year_level` varchar(20) NOT NULL,
  `email` varchar(100) NOT NULL,
  `username` varchar(50) NOT NULL,
  `password` varchar(255) NOT NULL,
  `profile_picture` varchar(255) DEFAULT 'default.jpg',
  `sessions_used` int(11) DEFAULT 0,
  `max_sessions` int(11) DEFAULT 25,
  `points` int(11) DEFAULT 0,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `students`
--

INSERT INTO `students` (`id`, `idno`, `lastname`, `firstname`, `middlename`, `course`, `year_level`, `email`, `username`, `password`, `profile_picture`, `sessions_used`, `max_sessions`, `points`, `created_at`) VALUES
(1, '22660070', 'Cutanda', 'John Jecu', 'Noval', '1', '3', 'jecu@123.com', 'jecu', 'pbkdf2:sha256:260000$HkNcBqYroUcODe0b$2ac1f536847205fda7b70563b85abfe4f98775aeec734422c8ccbb97e0d5a6e8', '22660070_1746102618_481704576_1196798168815530_8973883449594692050_n.jpg', 1, 32, 1, '2025-05-01 12:28:33'),
(2, '22660062', 'Colon', 'Lovella', 'Palen', 'Bachelor of Science in Mathematics', '3', 'lovella@123.com', 'lovella', 'pbkdf2:sha256:260000$x42k02mxZVPFowGH$06b806169e3c516dc6baf50732a61d030847fa6e1f52f9bccc27cc6d146224d0', 'default.jpg', 0, 25, 0, '2025-05-01 12:29:08'),
(3, '1232131', 'Colon', 'Camella', 'Palen', 'Bachelor of Science in Medical Technology', '1', 'camella@123.com', 'camella', 'pbkdf2:sha256:260000$tscJnisq48k9NZpo$d9efdbaee2b86ae3533ab9d4fe30579f1cd61d2dd2b05f7e69c6ad7424dcbc00', 'default.jpg', 0, 25, 1, '2025-05-01 12:29:30'),
(4, '12312312323', 'Lazaga', 'Bayot', 'ko', 'Bachelor of Science in Medical Technology', '1', 'Lazaga@123.com', 'Lazaga', 'pbkdf2:sha256:260000$qjE2U0P2bKCbfple$918bab2fdf0b8f1de08d23af12d7c1bab79ea6ca27046e578e92ec265bb1c155', 'default.jpg', 0, 25, 0, '2025-05-01 12:29:48'),
(5, '323213', 'Rivas', 'Mongol', 'Jud', 'Bachelor of Science in Criminology', '2', 'papskikoi@gmail.com', 'rivas', 'pbkdf2:sha256:260000$UkK72RpA0glnmX53$048ddb281f08d0fb18a9a694f31468adf26d7802f30e0115095cd4aff85ecd30', 'default.jpg', 0, 25, 0, '2025-05-01 12:30:07'),
(6, '092323', 'Cutanda', 'John Charles', 'Noval', 'Bachelor of Science in Medical Technology', '1', 'Cutanda@123.com', 'jc', 'pbkdf2:sha256:260000$Zg2yyquGRZgFsWzQ$eb464a61c5ee0a2cf5caf1f8b7694b1200f02733bdf8b6db578ec39dd15da945', 'default.jpg', 0, 25, 0, '2025-05-05 15:15:46');

-- --------------------------------------------------------

--
-- Table structure for table `system_logs`
--

CREATE TABLE `system_logs` (
  `id` int(11) NOT NULL,
  `action` varchar(50) NOT NULL,
  `description` text DEFAULT NULL,
  `user_id` int(11) DEFAULT NULL,
  `timestamp` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Indexes for dumped tables
--

--
-- Indexes for table `admins`
--
ALTER TABLE `admins`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `username` (`username`);

--
-- Indexes for table `announcements`
--
ALTER TABLE `announcements`
  ADD PRIMARY KEY (`id`);

--
-- Indexes for table `feedback`
--
ALTER TABLE `feedback`
  ADD PRIMARY KEY (`id`),
  ADD KEY `session_id` (`session_id`),
  ADD KEY `student_id` (`student_id`);

--
-- Indexes for table `lab_resources`
--
ALTER TABLE `lab_resources`
  ADD PRIMARY KEY (`id`);

--
-- Indexes for table `lab_schedules`
--
ALTER TABLE `lab_schedules`
  ADD PRIMARY KEY (`id`);

--
-- Indexes for table `pc_status`
--
ALTER TABLE `pc_status`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `lab_pc_idx` (`lab_room`,`pc_number`);

--
-- Indexes for table `points`
--
ALTER TABLE `points`
  ADD PRIMARY KEY (`id`),
  ADD KEY `student_id` (`student_id`);

--
-- Indexes for table `programming_languages`
--
ALTER TABLE `programming_languages`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `name` (`name`);

--
-- Indexes for table `reward_logs`
--
ALTER TABLE `reward_logs`
  ADD PRIMARY KEY (`id`),
  ADD KEY `student_id` (`student_id`),
  ADD KEY `admin_id` (`admin_id`);

--
-- Indexes for table `sessions`
--
ALTER TABLE `sessions`
  ADD PRIMARY KEY (`id`),
  ADD KEY `student_id` (`student_id`);

--
-- Indexes for table `students`
--
ALTER TABLE `students`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `idno` (`idno`),
  ADD UNIQUE KEY `email` (`email`),
  ADD UNIQUE KEY `username` (`username`);

--
-- Indexes for table `system_logs`
--
ALTER TABLE `system_logs`
  ADD PRIMARY KEY (`id`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `admins`
--
ALTER TABLE `admins`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- AUTO_INCREMENT for table `announcements`
--
ALTER TABLE `announcements`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- AUTO_INCREMENT for table `feedback`
--
ALTER TABLE `feedback`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- AUTO_INCREMENT for table `lab_resources`
--
ALTER TABLE `lab_resources`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=6;

--
-- AUTO_INCREMENT for table `lab_schedules`
--
ALTER TABLE `lab_schedules`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=11;

--
-- AUTO_INCREMENT for table `pc_status`
--
ALTER TABLE `pc_status`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=102;

--
-- AUTO_INCREMENT for table `points`
--
ALTER TABLE `points`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `programming_languages`
--
ALTER TABLE `programming_languages`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=9;

--
-- AUTO_INCREMENT for table `reward_logs`
--
ALTER TABLE `reward_logs`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `sessions`
--
ALTER TABLE `sessions`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=20;

--
-- AUTO_INCREMENT for table `students`
--
ALTER TABLE `students`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=7;

--
-- AUTO_INCREMENT for table `system_logs`
--
ALTER TABLE `system_logs`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- Constraints for dumped tables
--

--
-- Constraints for table `feedback`
--
ALTER TABLE `feedback`
  ADD CONSTRAINT `feedback_ibfk_1` FOREIGN KEY (`session_id`) REFERENCES `sessions` (`id`) ON DELETE CASCADE,
  ADD CONSTRAINT `feedback_ibfk_2` FOREIGN KEY (`student_id`) REFERENCES `students` (`id`) ON DELETE CASCADE;

--
-- Constraints for table `points`
--
ALTER TABLE `points`
  ADD CONSTRAINT `points_ibfk_1` FOREIGN KEY (`student_id`) REFERENCES `students` (`id`) ON DELETE CASCADE;

--
-- Constraints for table `reward_logs`
--
ALTER TABLE `reward_logs`
  ADD CONSTRAINT `reward_logs_ibfk_1` FOREIGN KEY (`student_id`) REFERENCES `students` (`id`),
  ADD CONSTRAINT `reward_logs_ibfk_2` FOREIGN KEY (`admin_id`) REFERENCES `admins` (`id`);

--
-- Constraints for table `sessions`
--
ALTER TABLE `sessions`
  ADD CONSTRAINT `sessions_ibfk_1` FOREIGN KEY (`student_id`) REFERENCES `students` (`id`) ON DELETE CASCADE;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
